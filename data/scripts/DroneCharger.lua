-- The Drone Charger: a landing pad that builds one drone, flies it and brings
-- it home to charge.
--
-- The pad is the only scripted thing here. Scripting the drone itself would
-- put a script on every drone in the prison, and the game rebuilds the whole
-- script API into Lua on every one of those calls, so the pad does the
-- thinking for the machine it owns. A prison has a handful of pads, and they
-- are the whole cost this adds.
--
-- The pad remembers its drone by the drone's own id, kept on the pad's
-- blackboard, and finds it again by looking at the drones within reach and
-- matching that id. Nothing is written on the drone itself but its name, and
-- that is the lease data/world.lua reads: a pad stamps its drone's name every
-- cycle, the world script takes the stamp off on its sweep, and a drone that
-- goes a whole sweep unstamped has lost its pad and is removed.
--
-- Two roles, chosen with the button on the pad:
--
--   Hauler    Carries the dead to the morgue, and clears rubbish when there
--             are no dead. Bodies come first and nothing else competes.
--   Predator  Patrols the ground its pad covers, or holds station on it, and
--             shocks any prisoner caught in misconduct.

local Get  = Object.GetProperty
local Set  = Object.SetProperty
local Find = Object.GetNearbyObjects
local safe = pcall or function(f, ...) return true, f(...) end

local MODEL     = { Hauler = "HaulerDrone", Predator = "PredatorDrone" }
local NEXT_ROLE = { Hauler = "Predator", Predator = "Hauler" }
local NEXT_DUTY = { Patrol = "Post", Post = "Patrol" }

-- The name a pad stamps on its drone. data/world.lua sweeps by it.
local MARK = "RobotDroneUnit"

local CYCLE       = 1.0   -- seconds between the pad's decisions
local FIND_EVERY  = 6     -- seconds between searches for the pad's own drone
local WORK_RANGE  = 30    -- tiles a drone may travel from its pad
local FIND_RANGE  = 50    -- tiles searched for it; wider than it can ever be
local DOCK_RANGE  = 1.4   -- tiles; this close to the pad the drone is docked
local ARRIVE      = 1.4   -- tiles; this close to a goal counts as arrived
local RENAV       = 3     -- seconds between repeats of a standing order
local STUCK_AFTER = 9     -- seconds without moving before an order is given up
local STUCK_MOVE  = 0.4   -- tiles; moving less than this is not moving

local FULL  = 100
local LOW   = 25          -- below this a drone breaks off and comes home
local DRAIN = 0.4         -- charge a second while flying
local FILL  = 7           -- charge a second while docked

local LOOK_EVERY     = 4  -- seconds between looks for work
local KINDS_PER_LOOK = 4  -- kinds of person searched on each of those looks

local STRIKE_RANGE      = 1.8
local STRIKE_EVERY      = 2.5   -- seconds between shocks
local STRIKE_BITE       = 0.06  -- of a whole life, per shock
local STRIKE_CEILING    = 0.8   -- a predator wounds and stops; it never finishes anyone
local MISCONDUCT_WINDOW = 45    -- seconds a prisoner stays a target after misconduct
local ROAM_EVERY        = 14    -- seconds a patrol holds a waypoint before picking another

local NONE = -1

-- The pad has a picture per model and per state: the Hauler's dark pad, the
-- Hauler's live one, then the Predator's pair.
local function pictureOf(model, live)
    return (model == "Predator" and 2 or 0) + (live and 1 or 0)
end

-- Every kind of person a hauler will lift the corpse of. The list is short on
-- purpose: it is also what data/world.lua searches to put down whatever an
-- abandoned drone was holding, and that has to stay cheap.
local BODY_KINDS = {
    "Prisoner", "Guard", "ArmedGuard", "RiotGuard", "Sniper", "DogHandler",
    "Workman", "Foreman", "Cook", "Janitor", "Gardener", "Doctor", "Orderly",
    "Paramedic", "Warden", "Chief", "Visitor", "Dog",
}

-- What the game writes down when a prisoner does something it counts against
-- them.
local MISCONDUCT = {
    "TimeOfLastMisconduct", "TimeOfLastMisconductStaffAssault",
    "TimeOfLastMisconductPrisonerAssault", "TimeOfLastMisconductMurders",
    "TimeOfLastMisconductEscapeAttempt", "TimeOfLastMisconductSeriousInjury",
}

local clock      = 0
local cycleTimer = math.random() * CYCLE
local findTimer  = FIND_EVERY
local lookTimer  = math.random() * LOOK_EVERY
local drone      = nil    -- the pad's own drone, held between cycles
local dressed    = ""     -- the model and duty the pad's buttons were last drawn for
local goalX, goalY        -- where the drone has been told to go
local navAt      = -RENAV
local lastX, lastY        -- where it was when it last moved
local movedAt    = 0
local roamAt     = -ROAM_EVERY
local strikeAt   = -STRIKE_EVERY
local kindTurn   = 0
local unliftable = {}     -- ids of things a pickup did not take on
local record     = {}     -- prisoner id -> their misconduct record when last looked at
local hot        = {}     -- prisoner id -> when this pad saw that record move
local shown      = ""

-------------------------------------------------------------------------------
-- Small helpers
-------------------------------------------------------------------------------

local function num(v, fallback)
    return tonumber(v) or fallback
end

local function role()
    local r = Get("Role")
    if r ~= "Predator" then return "Hauler" end
    return r
end

local function duty()
    local d = Get("Duty")
    if d ~= "Post" then return "Patrol" end
    return d
end

local function away(obj, x, y)
    local dx = num(obj.Pos.x, 0) - x
    local dy = num(obj.Pos.y, 0) - y
    return math.sqrt(dx * dx + dy * dy)
end

local function fromPad(obj)
    return away(obj, this.Pos.x, this.Pos.y)
end

local function slotOf(obj)
    return num(Get(obj, "Slot0.i"), NONE)
end

local function clearSlot(obj)
    Set(obj, "Slot0.i", NONE)
    Set(obj, "Slot0.u", NONE)
end

-- The one kind a search has to cover to find what the drone is holding or
-- going after. A kind the pad did not write down falls back to the whole list,
-- which only happens for a load carried across a version of the mod that did
-- not record it.
local function kindsFor(typ, what)
    if typ ~= nil and typ ~= "" then return { typ } end
    if what == "Rubbish" then return { "Garbage" } end
    return BODY_KINDS
end

-- Anything the drone is holding or going after is somewhere in the ground the
-- pad covers, so every one of these searches is made from the pad. Searching
-- from the drone instead would be cheaper and wrong: the game moves a carried
-- thing to its carrier for its own carriers, and a load picked up by hand may
-- simply stay where it was put down, which is a few tiles behind a drone that
-- has already flown on.
local function byId(kinds, wantI)
    for _, typ in ipairs(kinds) do
        for obj in pairs(Find(typ, WORK_RANGE) or {}) do
            local id = obj.Id
            if id and id.i == wantI then return obj, typ end
        end
    end
    return nil, nil
end

-------------------------------------------------------------------------------
-- The drone itself
-------------------------------------------------------------------------------

-- The pad's own drone, by the id on the pad's blackboard. A drone never flies
-- further than WORK_RANGE, and this looks further than that, so a search that
-- finds nothing means the drone is really gone rather than out of reach.
local function locate()
    local wantI = num(Get("DroneI"), NONE)
    if wantI == NONE then return nil end
    local wantU = num(Get("DroneU"), NONE)
    for obj in pairs(Find(MODEL[role()], FIND_RANGE) or {}) do
        local id = obj.Id
        if id and id.i == wantI and id.u == wantU then return obj end
    end
    return nil
end

-- Puts down whatever the drone is holding, wherever it is. Called before a
-- drone is scrapped and whenever its load stops making sense.
local function letGo(unit)
    local held = slotOf(unit)
    if held ~= NONE then
        local load = byId(kindsFor(Get("LoadType"), Get("LoadKind")), held)
        if load ~= nil and num(Get(load, "CarrierId.i"), NONE) == unit.Id.i then
            Set(load, "Loaded", false)
            Set(load, "CarrierId.i", NONE)
            Set(load, "CarrierId.u", NONE)
        end
        clearSlot(unit)
    end
    Set("LoadKind", "")
    Set("LoadType", "")
end

local function scrap()
    local wantI = num(Get("DroneI"), NONE)
    if wantI ~= NONE then
        -- Both models are looked at, because the drone standing here may be
        -- the one the pad has just been switched away from.
        for _, model in pairs(MODEL) do
            for obj in pairs(Find(model, FIND_RANGE) or {}) do
                local id = obj.Id
                if id and id.i == wantI and id.u == num(Get("DroneU"), NONE) then
                    letGo(obj)
                    obj.Delete()
                end
            end
        end
    end
    drone = nil
    Set("DroneI", NONE)
    Set("DroneU", NONE)
end

local function build()
    local unit = Object.Spawn(MODEL[role()], this.Pos.x, this.Pos.y)
    if unit == nil or unit.Id == nil then return nil end
    Set(unit, "Name", MARK)
    Set("DroneI", unit.Id.i)
    Set("DroneU", unit.Id.u)
    Set("Charge", FULL)
    Set("LoadKind", "")
    Set("LoadType", "")
    Set("TargetI", NONE)
    goalX, goalY = nil, nil
    return unit
end

-------------------------------------------------------------------------------
-- Flying
-------------------------------------------------------------------------------

local function forget()
    goalX, goalY = nil, nil
    movedAt = clock
end

-- Sends the drone to a point, and says nothing to it again until the point
-- moves or the standing order goes stale. Repeating an order every tick makes
-- the game throw the route away and find it again, which is dear and leaves
-- the drone shuffling on the spot.
local function fly(unit, x, y)
    -- Nothing is ever sent past the pad's reach, so a drone cannot end up
    -- further off than the pad searches for it.
    local dx, dy = x - this.Pos.x, y - this.Pos.y
    local out = math.sqrt(dx * dx + dy * dy)
    if out > WORK_RANGE then
        x = this.Pos.x + dx * WORK_RANGE / out
        y = this.Pos.y + dy * WORK_RANGE / out
    end
    if goalX == nil or math.abs(x - goalX) > 0.5 or math.abs(y - goalY) > 0.5
       or clock - navAt >= RENAV then
        goalX, goalY = x, y
        navAt = clock
        Object.NavigateTo(unit, x, y)
    end
end

-- True once the drone has stopped getting anywhere. An order to a point it
-- cannot reach is dropped rather than repeated for ever.
local function stuck(unit)
    local x, y = num(unit.Pos.x, 0), num(unit.Pos.y, 0)
    if lastX == nil or math.abs(x - lastX) > STUCK_MOVE or math.abs(y - lastY) > STUCK_MOVE then
        lastX, lastY, movedAt = x, y, clock
        return false
    end
    return clock - movedAt > STUCK_AFTER
end

-------------------------------------------------------------------------------
-- Carrying
-------------------------------------------------------------------------------

local function lift(unit, obj, what, typ)
    local id = obj.Id
    if id == nil then return false end
    Set(obj, "Loaded", true)
    Set(obj, "CarrierId.i", unit.Id.i)
    Set(obj, "CarrierId.u", unit.Id.u)
    -- The pickup is read back rather than assumed. Anything the game will not
    -- let go of is remembered and left alone, so a drone cannot spend the rest
    -- of the game reaching for the same thing.
    if num(Get(obj, "CarrierId.i"), NONE) ~= unit.Id.i then
        unliftable[id.i] = true
        return false
    end
    Set(unit, "Slot0.i", id.i)
    Set(unit, "Slot0.u", id.u)
    Set("LoadKind", what)
    Set("LoadType", typ)
    return true
end

-- What the drone is holding, moved with it by hand. The game draws what is in
-- a slot at the carrier's markers, and this keeps where the thing actually is
-- in step with where it is drawn. Returns nil when the drone is empty, or
-- when somebody else has taken what it was holding.
local function load(unit)
    local held = slotOf(unit)
    if held == NONE then return nil end
    local obj = byId(kindsFor(Get("LoadType"), Get("LoadKind")), held)
    if obj == nil then return nil end
    if num(Get(obj, "CarrierId.i"), NONE) ~= unit.Id.i then
        clearSlot(unit)
        Set("LoadKind", "")
        Set("LoadType", "")
        return nil
    end
    Set(obj, "Pos.x", unit.Pos.x)
    Set(obj, "Pos.y", unit.Pos.y)
    return obj
end

-------------------------------------------------------------------------------
-- The hauler
-------------------------------------------------------------------------------

-- A dead entity keeps its type but gains a cause of death and full damage.
local function isCorpse(obj)
    local cause = obj.DeathType
    if cause ~= nil and cause ~= "" and cause ~= "None" then return true end
    return num(obj.Damage, 0) >= 1
end

local function freeSlab()
    local best, near = nil, nil
    for slab, dist in pairs(Find("MorgueSlab", WORK_RANGE) or {}) do
        if slotOf(slab) == NONE then
            local d = num(dist, 0)
            if near == nil or d < near then best, near = slab, d end
        end
    end
    return best
end

-- The nearest corpse nobody is holding and nothing is resting on, with the
-- kind it was found under. Only a few kinds are searched each look, because a
-- search is the dearest thing a script asks the game for and nearly every
-- corpse in a prison is a prisoner's.
local function findBody()
    local kinds = { BODY_KINDS[1] }
    for _ = 1, KINDS_PER_LOOK do
        kindTurn = kindTurn % #BODY_KINDS + 1
        if kindTurn ~= 1 then table.insert(kinds, BODY_KINDS[kindTurn]) end
    end
    local best, bestKind, near = nil, nil, nil
    for _, kind in ipairs(kinds) do
        for obj, dist in pairs(Find(kind, WORK_RANGE) or {}) do
            local id = obj.Id
            if id and not unliftable[id.i] and obj.Loaded ~= true and isCorpse(obj) then
                local d = num(dist, 0)
                if near == nil or d < near then best, bestKind, near = obj, kind, d end
            end
        end
    end
    return best, bestKind
end

local function findRubbish()
    local best, near = nil, nil
    for obj, dist in pairs(Find("Garbage", WORK_RANGE) or {}) do
        local id = obj.Id
        if id and not unliftable[id.i] and obj.Loaded ~= true then
            local d = num(dist, 0)
            if near == nil or d < near then best, near = obj, d end
        end
    end
    return best
end

local function deliver(unit, body)
    local slab = freeSlab()
    if slab == nil then
        -- nowhere to put it: set it down here rather than hold it for ever
        letGo(unit)
        forget()
        return "Nowhere"
    end
    fly(unit, slab.Pos.x, slab.Pos.y)
    if away(unit, slab.Pos.x, slab.Pos.y) <= ARRIVE then
        Set(slab, "Slot0.i", body.Id.i)
        Set(slab, "Slot0.u", body.Id.u)
        Set(body, "CarrierId.i", slab.Id.i)
        Set(body, "CarrierId.u", slab.Id.u)
        Set(body, "Pos.x", slab.Pos.x)
        Set(body, "Pos.y", slab.Pos.y)
        clearSlot(unit)
        Set("LoadKind", "")
        Set("LoadType", "")
        forget()
    elseif stuck(unit) then
        letGo(unit)
        forget()
    end
    return "Carrying"
end

local function recycle(unit, rubbish)
    fly(unit, this.Pos.x, this.Pos.y)
    if fromPad(unit) <= DOCK_RANGE + 0.8 then
        clearSlot(unit)
        Set("LoadKind", "")
        Set("LoadType", "")
        rubbish.Delete()
        forget()
    elseif stuck(unit) then
        letGo(unit)
        forget()
    end
    return "Clearing"
end

local function fetch(unit)
    local wantI = num(Get("TargetI"), NONE)
    if wantI == NONE then return nil end
    local what = Get("TargetKind") or "Rubbish"
    local obj, typ = byId(kindsFor(Get("TargetType"), what), wantI)
    if obj == nil then
        Set("TargetI", NONE)
        return nil
    end
    if obj.Loaded == true then
        Set("TargetI", NONE)      -- somebody else got there first
        return nil
    end
    local x, y = num(obj.Pos.x, 0), num(obj.Pos.y, 0)
    fly(unit, x, y)
    if away(unit, x, y) <= ARRIVE then
        lift(unit, obj, what, typ)
        Set("TargetI", NONE)
        forget()
    elseif stuck(unit) then
        Set("TargetI", NONE)
        forget()
    end
    return what == "Body" and "Fetching" or "Clearing"
end

local function haul(unit, homeward)
    local held = load(unit)
    if held ~= nil then
        if Get("LoadKind") == "Body" then return deliver(unit, held) end
        return recycle(unit, held)
    end
    if homeward then return nil end

    -- Bodies first, always, and only while there is a slab free to take one.
    if lookTimer >= LOOK_EVERY then
        lookTimer = 0
        local target, typ, what = nil, nil, "Body"
        if freeSlab() ~= nil then target, typ = findBody() end
        if target == nil then
            target, typ, what = findRubbish(), "Garbage", "Rubbish"
        end
        if target ~= nil then
            Set("TargetI", target.Id.i)
            Set("TargetKind", what)
            Set("TargetType", typ)
            forget()
        else
            Set("TargetI", NONE)
        end
    end
    return fetch(unit)
end

-------------------------------------------------------------------------------
-- The predator
-------------------------------------------------------------------------------

-- The latest of the game's records of a prisoner's misconduct.
local function lastCaught(obj)
    local latest = 0
    for _, field in ipairs(MISCONDUCT) do
        local when = num(Get(obj, field), 0)
        if when > latest then latest = when end
    end
    return latest
end

-- Misconduct is spotted by watching those records move rather than by reading
-- the clock off them. Game.Time is how long the game has been running, and the
-- records are written on the prison's own clock, so nothing sensible comes of
-- subtracting one from the other. A record that is later than it was the last
-- time this pad looked at that prisoner is misconduct that has just happened,
-- whatever either clock says.
--
-- A prisoner seen for the first time only sets the mark to measure the next
-- look against. That is what stops a pad going after everybody with a history
-- the moment it is built or a save is loaded.
local function findTarget()
    local fresh = {}
    local best, near = nil, nil
    for obj, dist in pairs(Find("Prisoner", WORK_RANGE) or {}) do
        local id = obj.Id
        if id then
            local latest = lastCaught(obj)
            fresh[id.i] = latest
            if record[id.i] ~= nil and latest > record[id.i] then
                hot[id.i] = clock
            end
            if hot[id.i] ~= nil and clock - hot[id.i] > MISCONDUCT_WINDOW then
                hot[id.i] = nil
            end
            if hot[id.i] ~= nil and num(obj.Damage, 0) < STRIKE_CEILING and not isCorpse(obj) then
                local d = num(dist, 0)
                if near == nil or d < near then best, near = obj, d end
            end
        end
    end
    record = fresh
    return best
end

local function strike(unit, obj)
    if clock - strikeAt < STRIKE_EVERY then return end
    strikeAt = clock
    local hurt = num(Get(obj, "Damage"), 0)
    if hurt >= STRIKE_CEILING then return end
    Set(obj, "Damage", math.min(STRIKE_CEILING, hurt + STRIKE_BITE))
    -- The shock is what matters; the noise it makes is not worth a script
    -- error on a build of the game that spells the call differently.
    safe(function() Object.Sound(unit, "_Tools", "HitBy_Tazer") end)
end

-- Where a patrol goes next: to a prisoner it can see, and otherwise to a point
-- somewhere in the ground its pad covers.
local function roam(unit)
    if goalX ~= nil and clock - roamAt < ROAM_EVERY and not stuck(unit) then return end
    roamAt = clock
    forget()
    local pick, seen = nil, 0
    for obj in pairs(Find("Prisoner", WORK_RANGE) or {}) do
        seen = seen + 1
        if math.random(seen) == 1 then pick = obj end
    end
    if pick ~= nil then
        fly(unit, num(pick.Pos.x, this.Pos.x), num(pick.Pos.y, this.Pos.y))
        return
    end
    local angle = math.random() * math.pi * 2
    local reach = WORK_RANGE * (0.3 + math.random() * 0.7)
    fly(unit, this.Pos.x + math.cos(angle) * reach, this.Pos.y + math.sin(angle) * reach)
end

local function prowl(unit, homeward)
    if homeward then
        Set("TargetI", NONE)
        return nil
    end
    if lookTimer >= LOOK_EVERY then
        lookTimer = 0
        local target = findTarget()
        Set("TargetI", target ~= nil and target.Id.i or NONE)
    end

    local wantI = num(Get("TargetI"), NONE)
    if wantI ~= NONE then
        local obj = byId({ "Prisoner" }, wantI)
        if obj ~= nil then
            local x, y = num(obj.Pos.x, 0), num(obj.Pos.y, 0)
            fly(unit, x, y)
            if away(unit, x, y) <= STRIKE_RANGE then
                strike(unit, obj)
            elseif stuck(unit) then
                Set("TargetI", NONE)
                forget()
            end
            return "Chasing"
        end
        Set("TargetI", NONE)
    end

    if duty() == "Post" then
        -- holding the ground round the pad: near enough to watch it, never on it
        if fromPad(unit) > 4 then fly(unit, this.Pos.x + 2.5, this.Pos.y + 2.5) end
        return "Holding"
    end
    roam(unit)
    return "Patrolling"
end

-------------------------------------------------------------------------------
-- The pad
-------------------------------------------------------------------------------

local function tell(state)
    local key = "tooltip_DroneCharger_" .. state
    local charge = math.floor(num(Get("Charge"), FULL))
    local line = key .. charge
    if line ~= shown then
        shown = line
        this.Tooltip = { key, charge, "C" }
    end
end

-- The pad's own buttons. They are put on afresh rather than remembered,
-- because the window they sit in is built again every time the pad is
-- selected and after every load.
local function buttons()
    dressed = role() .. duty()
    safe(function()
        this.AddInterfaceComponent("DroneRole", "Button", "button_DroneRole_" .. role())
        if role() == "Predator" then
            this.AddInterfaceComponent("DroneDuty", "Button", "button_DroneDuty_" .. duty())
        else
            this.RemoveInterfaceComponent("DroneDuty")
        end
    end)
end

function ButtonPressed_DroneRole()
    Set("Role", NEXT_ROLE[role()])
    Set("TargetI", NONE)
    scrap()
    buttons()
end

function ButtonPressed_DroneDuty()
    Set("Duty", NEXT_DUTY[duty()])
    Set("TargetI", NONE)
    forget()
    buttons()
end

function Create()
    Set("Role", "Hauler")
    Set("Duty", "Patrol")
    Set("Charge", FULL)
    Set("LoadKind", "")
    Set("LoadType", "")
    Set("TargetI", NONE)
    Set("DroneI", NONE)
    Set("DroneU", NONE)
    this.SubType = 0
    buttons()
    tell("Building")
end

local function think(dt)
    if dressed ~= role() .. duty() then buttons() end
    if drone == nil or findTimer >= FIND_EVERY then
        findTimer = 0
        drone = locate()
    end
    if drone == nil then
        drone = build()
        this.SubType = pictureOf(role(), false)
        tell("Building")
        return
    end

    -- the lease: every cycle the pad says this drone is still its own
    Set(drone, "Name", MARK)

    local charge = num(Get("Charge"), FULL)
    local docked = fromPad(drone) <= DOCK_RANGE
    if docked then
        charge = math.min(FULL, charge + FILL * dt)
    else
        charge = math.max(0, charge - DRAIN * dt)
    end
    Set("Charge", charge)
    this.SubType = pictureOf(role(), docked and charge < FULL)

    -- A drone that has run its charge down comes home and stays on the pad
    -- until it is full again. One already holding something finishes with it
    -- first, so nothing is left lying where nobody will look for it.
    local homeward = charge <= LOW
    if docked and charge < FULL and slotOf(drone) == NONE then
        tell("Charging")
        return
    end

    local state
    if role() == "Hauler" then
        state = haul(drone, homeward)
    else
        state = prowl(drone, homeward)
    end
    if state == nil then
        if homeward or fromPad(drone) > DOCK_RANGE then
            fly(drone, this.Pos.x, this.Pos.y)
        end
        state = homeward and "Returning" or "Idle"
    end
    tell(state)
end

function Update(timePassed)
    local dt = num(timePassed, 0)
    clock = clock + dt
    cycleTimer = cycleTimer + dt
    findTimer = findTimer + dt
    lookTimer = lookTimer + dt
    if cycleTimer < CYCLE then return end
    local step = cycleTimer
    cycleTimer = 0
    local ok, err = safe(think, step)
    if not ok then Set("LastError", tostring(err)) end
end

-- The game hands a script every object a search finds as a global named for
-- the object's type and id, and never takes one back, so a script that
-- searches holds on to everyone it has ever found. Every FORGET_EVERY seconds
-- those globals are cleared, and Lua's own collector frees what they held. The
-- pad holds its own drone between updates, so that one is looked up again on
-- the next cycle rather than kept through the clearing.
local FORGET_EVERY = 20
local forgetTimer = math.random() * FORGET_EVERY
local runUpdate = Update
function Update(timePassed)
    forgetTimer = forgetTimer + (tonumber(timePassed) or 0)
    if forgetTimer >= FORGET_EVERY then
        forgetTimer = 0
        if _G ~= nil then
            for name, value in pairs(_G) do
                if type(value) == "table" and type(name) == "string" and name:find("i%-?%d+u%-?%d+$") then
                    _G[name] = nil
                end
            end
        end
        drone = nil
        findTimer = FIND_EVERY
    end
    return runUpdate(timePassed)
end
