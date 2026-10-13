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
--
-- A Hauler never looks for the dead itself. A search hands back a full script
-- record of every living person of the kind asked for, and a pad asking every
-- few seconds was most of what a big prison spent on its scripts. The world
-- script makes one search for the whole map and writes a body on each pad
-- with a drone free to fetch it, as BodyI, BodyU, BodyType, BodyX and BodyY.
-- A body can lie anywhere on the map and the slab it goes to can be anywhere
-- too, so a Hauler flies wherever the body is; rubbish is still only cleared
-- within the pad's own ground.
--
-- A Predator does not look over its ground itself either. Predators standing
-- together would each search the same prisoners every few seconds, so the
-- world script looks once for all of them and writes on each pad the prisoner
-- caught in misconduct to go after, as TargetI, TargetX and TargetY, and a
-- prisoner to patrol towards, as RoamI, RoamX and RoamY. Only once a drone is
-- on its quarry does it look for itself, and then only a few tiles round.

local Get  = Object.GetProperty
local Set  = Object.SetProperty
local Find = Object.GetNearbyObjects
local safe = pcall or function(f, ...) return true, f(...) end

local MODEL = { Hauler = "HaulerDrone", Predator = "PredatorDrone" }

-- The one button on the pad walks through these, in this order. Moving
-- between the two Predator duties keeps the drone; moving into or out of
-- Hauler scraps it and builds the other model.
local NEXT_MODE = { Hauler = "Patrol", Patrol = "Post", Post = "Hauler" }

-- The name a pad stamps on its drone. data/world.lua sweeps by it.
local MARK = "RobotDroneUnit"
-- The name every pad carries, which is how data/world.lua finds one to search
-- the map from.
local PAD_MARK = "RobotDronePad"

local CYCLE       = 1.0   -- seconds between the pad's decisions
local WORK_RANGE  = 30    -- tiles from its pad that a drone clears rubbish or patrols
local WHOLE_MAP   = 2000  -- tiles; wider than any map
local DOCK_RANGE  = 1.4   -- tiles; this close to the pad the drone is docked
local ARRIVE      = 1.4   -- tiles; this close to a goal counts as arrived
local RENAV       = 3     -- seconds between repeats of a standing order
local STUCK_AFTER = 9     -- seconds without moving before an order is given up
local STUCK_MOVE  = 0.4   -- tiles; moving less than this is not moving

local FULL  = 100
local LOW   = 25          -- below this a drone breaks off and comes home
local DRAIN = 0.4         -- charge a second while flying
local FILL  = 7           -- charge a second while docked

local LOOK_EVERY     = 4  -- seconds between looks for rubbish

local STRIKE_RANGE      = 1.8
local STRIKE_EVERY      = 2.5   -- seconds between shocks
local STRIKE_BITE       = 0.06  -- of a whole life, per shock
local STRIKE_CEILING    = 0.8   -- a predator wounds and stops; it never finishes anyone
local ROAM_EVERY        = 14    -- seconds a patrol holds a waypoint before picking another
local TRACK_REACH       = 3     -- tiles; how far round itself a drone on its quarry looks for it

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

local clock      = 0
local cycleTimer = math.random() * CYCLE
local lookTimer  = math.random() * LOOK_EVERY
local drone      = nil    -- the pad's own drone, held between cycles
local droneOut   = nil    -- how far from the pad the drone was when last seen
local carried    = nil    -- what the drone is holding, held between cycles
local aimed      = nil    -- the rubbish the drone is flying to, held between cycles
local slab       = nil    -- the slab the drone is taking a body to
local ready      = false  -- whether the pad's button has been put on since loading
local shownMode  = ""     -- the mode the button last said
local goalX, goalY        -- where the drone has been told to go
local navAt      = -RENAV
local lastX, lastY        -- where it was when it last moved
local movedAt    = 0
local roamAt     = -ROAM_EVERY
local strikeAt   = -STRIKE_EVERY
local unliftable = {}     -- ids of things a pickup did not take on
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

local function mode()
    if role() == "Hauler" then return "Hauler" end
    return duty()
end

local function away(obj, x, y)
    local dx = num(obj.Pos.x, 0) - x
    local dy = num(obj.Pos.y, 0) - y
    return math.sqrt(dx * dx + dy * dy)
end

local function fromPad(obj)
    return away(obj, this.Pos.x, this.Pos.y)
end

-- Where something held from an earlier cycle stands now, or nil once it has
-- been taken down. A furnace clears and rebuilds the slabs inside it, so a
-- slab chosen a cycle ago can be gone by the next.
local function whereIs(obj)
    local pos = obj.Pos
    local x, y = pos and num(pos.x, nil), pos and num(pos.y, nil)
    if x == nil or y == nil then return nil end
    return x, y
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

-- The last resort for finding a thing by id: every one of its kind on the
-- map. It hands back a full record of each, so it only runs when the look
-- round the drone below has already come up empty.
local function byId(kinds, wantI)
    for _, typ in ipairs(kinds) do
        for obj in pairs(Find(typ, WHOLE_MAP) or {}) do
            local id = obj.Id
            if id and id.i == wantI then return obj, typ end
        end
    end
    return nil, nil
end

-- The look made round the drone, only as far as the thing can be from it,
-- and the whole map when that turns nothing up. A search hands back a full
-- record of everyone of that kind in reach, so a look round the drone costs a
-- handful of records where the map would cost hundreds.
local NEAR_SLACK = 4      -- tiles past where the thing was last seen
local LOAD_REACH = 8      -- tiles; a load was put at the drone a cycle ago

local function byIdNear(unit, kinds, wantI, reach)
    if unit ~= nil and reach ~= nil and #kinds == 1 then
        local typ = kinds[1]
        for obj in pairs(Find(unit, typ, reach) or {}) do
            local id = obj.Id
            if id and id.i == wantI then return obj, typ end
        end
    end
    return byId(kinds, wantI)
end

-------------------------------------------------------------------------------
-- The drone itself
-------------------------------------------------------------------------------

-- The pad's own drone, by the id on the pad's blackboard. It is looked for
-- first a little past where it was last seen, which on the pad is a search of
-- a few tiles, and over the whole map only when that finds nothing, so a
-- search that finds nothing means the drone is really gone.
local function locate()
    local wantI = num(Get("DroneI"), NONE)
    if wantI == NONE then return nil end
    local wantU = num(Get("DroneU"), NONE)
    local function look(reach)
        for obj in pairs(Find(MODEL[role()], reach) or {}) do
            local id = obj.Id
            if id and id.i == wantI and id.u == wantU then return obj end
        end
        return nil
    end
    if droneOut ~= nil then
        local found = look(droneOut + 12)
        if found ~= nil then return found end
    end
    return look(WHOLE_MAP)
end

-- Puts down whatever the drone is holding, wherever it is. Called before a
-- drone is scrapped and whenever its load stops making sense.
local function letGo(unit)
    local held = slotOf(unit)
    if held ~= NONE then
        local load = carried
        if load == nil or load.Id == nil or load.Id.i ~= held then
            load = byIdNear(unit, kindsFor(Get("LoadType"), Get("LoadKind")), held, LOAD_REACH)
        end
        if load ~= nil and num(Get(load, "CarrierId.i"), NONE) == unit.Id.i then
            Set(load, "Loaded", false)
            Set(load, "CarrierId.i", NONE)
            Set(load, "CarrierId.u", NONE)
        end
        clearSlot(unit)
    end
    carried, slab = nil, nil
    Set("SlabI", NONE)
    Set("LoadKind", "")
    Set("LoadType", "")
end

local function scrap()
    local wantI = num(Get("DroneI"), NONE)
    if wantI ~= NONE then
        -- Both models are looked at, because the drone standing here may be
        -- the one the pad has just been switched away from.
        for _, model in pairs(MODEL) do
            for obj in pairs(Find(model, WHOLE_MAP) or {}) do
                local id = obj.Id
                if id and id.i == wantI and id.u == num(Get("DroneU"), NONE) then
                    letGo(obj)
                    obj.Delete()
                end
            end
        end
    end
    drone, droneOut = nil, nil
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
    droneOut = 0
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
local function fly(unit, x, y, anywhere)
    -- Rubbish and a patrol stay in the pad's own ground. A body and the slab
    -- it goes to can be anywhere, and those orders say so.
    if not anywhere then
        local dx, dy = x - this.Pos.x, y - this.Pos.y
        local out = math.sqrt(dx * dx + dy * dy)
        if out > WORK_RANGE then
            x = this.Pos.x + dx * WORK_RANGE / out
            y = this.Pos.y + dy * WORK_RANGE / out
        end
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

-- A body is a person whose Damage has reached 1. That is the only test: the
-- game hands a script a DeathType for the living as well as the dead, so
-- reading one says nothing about whether anybody has died.
local function isCorpse(obj)
    return num(obj.Damage, 0) >= 1
end

-- What the drone is holding, moved with it by hand. The game draws what is in
-- a slot at the carrier's markers, and this keeps where the thing actually is
-- in step with where it is drawn. Returns nil when the drone is empty, or
-- when somebody else has taken what it was holding.
--
-- The load is kept between cycles and only looked for again after the pad has
-- cleared the game's globals, so a drone crossing the prison does not ask for
-- every prisoner under it once a second.
local function load(unit)
    local held = slotOf(unit)
    if held == NONE then
        carried = nil
        return nil
    end
    local obj = carried
    if obj == nil or obj.Id == nil or obj.Id.i ~= held then
        obj = byIdNear(unit, kindsFor(Get("LoadType"), Get("LoadKind")), held, LOAD_REACH)
    end
    if obj == nil or num(Get(obj, "CarrierId.i"), NONE) ~= unit.Id.i then
        -- gone, or somebody else has it now
        clearSlot(unit)
        carried, slab = nil, nil
        Set("LoadKind", "")
        Set("LoadType", "")
        return nil
    end
    carried = obj
    if Get("LoadKind") == "Body" and not isCorpse(obj) then
        -- A robot the Uplink has repaired is no longer a body. Set it down
        -- where it is rather than carry it to a slab.
        letGo(unit)
        return nil
    end
    Set(obj, "Pos.x", unit.Pos.x)
    Set(obj, "Pos.y", unit.Pos.y)
    return obj
end

-------------------------------------------------------------------------------
-- The hauler
-------------------------------------------------------------------------------

-- The free slab nearest the drone, anywhere on the map. A prison holds a
-- dozen slabs or so, so this is a cheap search however wide it is.
local function nearestSlab(unit)
    local best, near = nil, nil
    for each, dist in pairs(Find(unit, "MorgueSlab", WHOLE_MAP) or {}) do
        if slotOf(each) == NONE then
            local d = num(dist, 0)
            if near == nil or d < near then best, near = each, d end
        end
    end
    return best
end

-- The body the world script has handed this pad, if any.
local function assigned()
    local wantI = num(Get("BodyI"), NONE)
    if wantI == NONE then return nil end
    return wantI
end

-- Hands the body back. A body the drone could not get to is named in
-- BodyFail, and the world script leaves it for a while before handing it to
-- anyone again.
local function release(failed)
    local wantI = assigned()
    Set("BodyI", NONE)
    if failed and wantI ~= nil then Set("BodyFail", wantI) end
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

-- Takes a body to the free slab nearest the drone. The slab is chosen once
-- for the trip and kept, and chosen again only if somebody fills it first.
-- The slab the world script handed this pad along with its body, and where
-- it stands.
local function assignedSlab()
    local wantI = num(Get("SlabI"), NONE)
    local x, y = num(Get("SlabX"), nil), num(Get("SlabY"), nil)
    if wantI == NONE or x == nil or y == nil then return nil end
    return wantI, x, y
end

-- Takes a body to the slab the world script chose for it, which is found on
-- arrival with a search a couple of tiles across. A slab somebody else has
-- filled in the meantime, or a body lifted before slabs were handed out, goes
-- to the free slab nearest the drone instead.
local function deliver(unit, body)
    if slab ~= nil and (whereIs(slab) == nil or slotOf(slab) ~= NONE) then slab = nil end
    if slab == nil then
        local wantI, x, y = assignedSlab()
        if wantI ~= nil then
            fly(unit, x, y, true)
            if away(unit, x, y) > ARRIVE then
                if stuck(unit) then
                    Set("SlabI", NONE)
                    forget()
                end
                return "Carrying"
            end
            for each in pairs(Find(unit, "MorgueSlab", ARRIVE + 1.5) or {}) do
                local id = each.Id
                if id and id.i == wantI and slotOf(each) == NONE then slab = each break end
            end
            Set("SlabI", NONE)
        end
        if slab == nil then slab = nearestSlab(unit) end
    end
    if slab == nil then
        -- nowhere to put it: set it down here rather than hold it for ever
        letGo(unit)
        forget()
        return "Nowhere"
    end
    local sx, sy = whereIs(slab)
    fly(unit, sx, sy, true)
    if away(unit, sx, sy) <= ARRIVE then
        Set(slab, "Slot0.i", body.Id.i)
        Set(slab, "Slot0.u", body.Id.u)
        Set(body, "CarrierId.i", slab.Id.i)
        Set(body, "CarrierId.u", slab.Id.u)
        Set(body, "Pos.x", sx)
        Set(body, "Pos.y", sy)
        clearSlot(unit)
        carried, slab = nil, nil
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
        carried = nil
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

-- Flies to the body the world script handed this pad and lifts it. The body
-- is looked for only once the drone is over it, and only a few tiles round,
-- so the whole trip costs one short search.
--
-- A body can lie where nobody can stand, against a wall or part way into
-- one, and the game routes nobody onto a spot like that. So a drone held up
-- short of a body lifts it from where it stopped, when that is near enough to
-- reach, and otherwise makes for each spot beside the body in turn before it
-- gives the body back.
local REACH_OVER = 3      -- tiles; a drone held up this near a body lifts it from there
local BESIDE = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 }, { 1, 1 }, { -1, 1 }, { 1, -1 }, { -1, -1 } }
local besideOf = NONE     -- the body being come at from beside
local beside   = 0        -- which spot beside it; none while making for the body itself

local function fetchBody(unit, wantI)
    local x, y = num(Get("BodyX"), nil), num(Get("BodyY"), nil)
    if x == nil or y == nil then
        release(false)
        return nil
    end
    if besideOf ~= wantI then besideOf, beside = wantI, 0 end
    local step = BESIDE[beside]
    if step ~= nil then
        fly(unit, x + step[1], y + step[2], true)
    else
        fly(unit, x, y, true)
    end
    local gap = away(unit, x, y)
    if gap > ARRIVE then
        if not stuck(unit) then return "Fetching" end
        if gap > REACH_OVER then
            beside = beside + 1
            if beside > #BESIDE then
                besideOf = NONE
                release(true)
            end
            forget()
            return "Fetching"
        end
    end
    local typ = Get("BodyType") or "Prisoner"
    local body = nil
    for obj in pairs(Find(unit, typ, math.max(gap, ARRIVE) + 1.5) or {}) do
        local id = obj.Id
        if id and id.i == wantI then body = obj break end
    end
    if body == nil or unliftable[wantI] then
        release(true)            -- it was not where the world script saw it
    elseif body.Loaded == true or not isCorpse(body) then
        release(false)           -- somebody else has it, or it is no longer a body
    elseif lift(unit, body, "Body", typ) then
        carried = body
        release(false)
    else
        release(true)
    end
    besideOf = NONE
    forget()
    return "Fetching"
end

-- How far round the drone the thing it is flying to can be: where it was sent,
-- which is where that thing stood, and a little more. Nil when it was sent
-- nowhere.
local function goalReach(unit)
    if goalX == nil then return nil end
    return away(unit, goalX, goalY) + NEAR_SLACK
end

-- A target the look has just found is the one the pad would find again, so
-- it is used as it is rather than searched for twice in one cycle. Only
-- rubbish comes through here; bodies are the world script's to hand out.
--
-- The target is kept from one cycle to the next and read where it stands
-- now, the way the load is, and searched for again only once it reads as
-- standing nowhere or the pad's globals have been cleared. A drone that
-- cannot get to its rubbish sits on its pad going after it, and searching
-- for it every cycle cost more than the rest of the pad put together.
local function fetch(unit, found)
    local wantI = num(Get("TargetI"), NONE)
    if wantI == NONE then return nil end
    if Get("TargetKind") == "Body" then
        -- a body target written by a version of the mod that looked for its own
        Set("TargetI", NONE)
        return nil
    end
    local obj = found
    if obj == nil or obj.Id == nil or obj.Id.i ~= wantI then
        obj = aimed
        if obj == nil or obj.Id == nil or obj.Id.i ~= wantI or whereIs(obj) == nil then
            obj = byIdNear(unit, { "Garbage" }, wantI, goalReach(unit))
        end
    end
    aimed = obj
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
        if lift(unit, obj, "Rubbish", "Garbage") then carried = obj end
        Set("TargetI", NONE)
        forget()
    elseif stuck(unit) then
        Set("TargetI", NONE)
        forget()
    end
    return "Clearing"
end

local function haul(unit, homeward)
    local held = load(unit)
    if held ~= nil then
        if Get("LoadKind") == "Body" then return deliver(unit, held) end
        return recycle(unit, held)
    end
    if homeward then
        release(false)           -- somebody else can have it
        return nil
    end

    -- Bodies first, always: a body handed to this pad drops whatever rubbish
    -- the drone was on its way to.
    local wantI = assigned()
    if wantI ~= nil then
        if num(Get("TargetI"), NONE) ~= NONE then
            Set("TargetI", NONE)
            forget()
        end
        return fetchBody(unit, wantI)
    end

    local target = nil
    if lookTimer >= LOOK_EVERY then
        lookTimer = 0
        target = findRubbish()
        if target ~= nil then
            Set("TargetI", target.Id.i)
            Set("TargetKind", "Rubbish")
            Set("TargetType", "Garbage")
            forget()
        else
            Set("TargetI", NONE)
        end
    end
    return fetch(unit, target)
end

-------------------------------------------------------------------------------
-- The predator
-------------------------------------------------------------------------------

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

-- Where a patrol goes next: to the prisoner in its ground the world script
-- last picked for it, and otherwise to a point somewhere in that ground.
local function roam(unit)
    if goalX ~= nil and clock - roamAt < ROAM_EVERY and not stuck(unit) then return end
    roamAt = clock
    forget()
    if num(Get("RoamI"), NONE) ~= NONE then
        local x, y = num(Get("RoamX"), nil), num(Get("RoamY"), nil)
        if x ~= nil and y ~= nil then
            fly(unit, x, y)
            return
        end
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

    -- The prisoner the world script set this pad on, and where it stood at the
    -- last look. The drone makes for that spot, and near it, whenever it could
    -- shock again, looks a few tiles round itself for the prisoner.
    local wantI = num(Get("TargetI"), NONE)
    local x, y = num(Get("TargetX"), nil), num(Get("TargetY"), nil)
    if wantI ~= NONE and x ~= nil and y ~= nil then
        local obj = nil
        if clock - strikeAt >= STRIKE_EVERY and away(unit, x, y) <= TRACK_REACH * 2 then
            for each in pairs(Find(unit, "Prisoner", TRACK_REACH) or {}) do
                local id = each.Id
                if id and id.i == wantI then obj = each break end
            end
        end
        if obj ~= nil then
            x, y = num(obj.Pos.x, x), num(obj.Pos.y, y)
            Set("TargetX", x)
            Set("TargetY", y)
        end
        fly(unit, x, y)
        if obj ~= nil and away(unit, x, y) <= STRIKE_RANGE then
            strike(unit, obj)
        elseif stuck(unit) then
            Set("TargetI", NONE)
            forget()
        end
        return "Chasing"
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

-- The pad's one button. The game keeps no interface on an object across a
-- load, so it is put on once each time the script starts, and the game calls
-- <component name>Clicked on this script when it is pressed. Writing a
-- caption is a call into the game, so it is only written when it changes.
local function showMode()
    local now = mode()
    if now == shownMode then return end
    shownMode = now
    this.SetInterfaceCaption("DroneMode", "button_DroneMode_" .. now)
end

local function dress()
    ready = true
    shownMode = mode()
    -- the pad's name is how the world script finds one to search the map from
    Set("Name", PAD_MARK)
    Interface.AddComponent(this, "DroneMode", "Button", "button_DroneMode_" .. shownMode)
end

-- Hauler, then Predator on Patrol, then Predator on Guard Post, then round
-- again. The model only changes going into or out of Hauler, and only then is
-- the drone scrapped, putting down whatever it holds.
function DroneModeClicked()
    local from = mode()
    local to = NEXT_MODE[from]
    Set("TargetI", NONE)
    release(false)
    if to == "Hauler" then
        Set("Role", "Hauler")
    else
        Set("Role", "Predator")
        Set("Duty", to)
    end
    if (from == "Hauler") ~= (to == "Hauler") then
        scrap()
    else
        forget()
    end
    showMode()
end

function Create()
    Set("Role", "Hauler")
    Set("Duty", "Patrol")
    Set("Charge", FULL)
    Set("LoadKind", "")
    Set("LoadType", "")
    Set("TargetI", NONE)
    Set("BodyI", NONE)
    Set("BodyFail", NONE)
    Set("SlabI", NONE)
    Set("DroneI", NONE)
    Set("DroneU", NONE)
    this.SubType = 0
    tell("Building")
end

local function think(dt)
    if not ready then dress() end
    -- The drone is held from one cycle to the next and only looked for again
    -- once it reads as standing nowhere, which is what a deleted object does,
    -- so a pad whose drone is still there never searches for it.
    if drone ~= nil and whereIs(drone) == nil then drone = nil end
    if drone == nil then drone = locate() end
    if drone == nil then
        drone = build()
        this.SubType = pictureOf(role(), false)
        tell("Building")
        return
    end

    -- the lease: every cycle the pad says this drone is still its own
    Set(drone, "Name", MARK)
    droneOut = fromPad(drone)

    -- No blow a drone takes shows, but a live cable and a deep freeze wear at
    -- whatever stands in them however tough it is. The pad mends its drone
    -- every cycle, which also brings back one that has gone down.
    if num(Get(drone, "Damage"), 0) > 0 then Set(drone, "Damage", 0) end

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
    lookTimer = lookTimer + dt
    if cycleTimer < CYCLE then return end
    local step = cycleTimer
    cycleTimer = 0
    local ok, err = safe(think, step)
    if not ok then
        Set("LastError", tostring(err))
        -- The trip is started again from what the pad can see, so something
        -- that has gone from under it cannot hold the drone where it is for
        -- good.
        carried, slab, aimed = nil, nil, nil
        forget()
    end
end

-- The game hands a script every object a search finds as a global named for
-- the object's type and id, and never takes one back, so a script that
-- searches holds on to everyone it has ever found. Every FORGET_EVERY seconds
-- those globals are cleared, and Lua's own collector frees what they held. The
-- pad holds its own drone between updates, so that one is looked up again on
-- the next cycle rather than kept through the clearing.
--
-- Drones and slabs keep theirs. The pad holds its own drone and the slab it is
-- taking a body to from one cycle to the next, and there are a few dozen of
-- either in a prison at most.
local FORGET_EVERY = 20
local forgetTimer = math.random() * FORGET_EVERY
local runUpdate = Update
function Update(timePassed)
    forgetTimer = forgetTimer + (tonumber(timePassed) or 0)
    if forgetTimer >= FORGET_EVERY then
        forgetTimer = 0
        if _G ~= nil then
            for name, value in pairs(_G) do
                if type(value) == "table" and type(name) == "string" and name:find("i%-?%d+u%-?%d+$")
                    and not name:find("^HaulerDrone") and not name:find("^PredatorDrone")
                    and not name:find("^MorgueSlab") then
                    _G[name] = nil
                end
            end
        end
        carried, aimed = nil, nil
    end
    return runUpdate(timePassed)
end
