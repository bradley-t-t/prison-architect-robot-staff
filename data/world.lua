-- Robot Staff: the mod's world script. It removes drones whose pad has gone,
-- finds the dead and hands them to the Haulers, and lets up anybody alive it
-- finds held down on a morgue slab.
--
-- A drone is flown by its Drone Charger and has no script of its own, so when
-- the pad is dismantled or destroyed the drone is left hanging where it is,
-- with nothing left to tell it to move or to take away whatever it is
-- holding. Nothing on the drone points back at the pad that owned it, and
-- there is no way to ask the game for the object behind an id, so the drone
-- cannot be asked whose it was.
--
-- What it can be asked is its name, and that is enough. A pad writes MARK on
-- its drone every second. This script takes the mark off on every sweep, by
-- renaming MARK to SPENT, and removes anything still called SPENT when the
-- next sweep comes round. A pad that is still standing puts its mark back
-- within a second, so its drone is never called SPENT when a sweep arrives;
-- a drone with no pad behind it is never marked again and goes on the sweep
-- after the one that took its mark off.
--
-- The game finds an object by name one at a time and gives no way to walk a
-- list, so both passes work by draining one name into another.
--
-- The dead are found here rather than by each pad. The game keeps no list of
-- the dead: a body is a person of some kind whose Damage has reached 1, so the
-- only way to find one is to search for every person of that kind, and a
-- search hands back a full script record of each, the living included. The
-- game compiles each of those records as it builds it, which costs a
-- millisecond or more apiece, so one search of every prisoner on a big map
-- stalls the game for most of a second.
--
-- So the map is searched a little at a time. The prison's lights stand in
-- every room and yard, and one light near the middle of each square of the
-- map, with more wherever a light would otherwise be left out, is a point to
-- search round. One point is searched every few seconds, for prisoners and
-- for one other kind of person in turn, and a whole pass of the map takes a
-- minute or so. What a pass finds is remembered, and every few seconds each
-- Hauler free to fly is handed the body nearest its pad. A body stays
-- remembered until it is handed out or a later pass finds it gone, so no body
-- is left lying however long it has been there.

local Get  = Object.GetProperty
local Set  = Object.SetProperty
local Find = Object.GetNearbyObjects

local MARK     = "RobotDroneUnit"    -- a pad's mark on the drone it owns
local SPENT    = "RobotDroneUnit2"   -- the mark taken off, one sweep from removal
local PAD_MARK = "RobotDronePad"     -- the name every pad carries

local SWEEP = 15    -- seconds between sweeps; fifteen times the pad's own cycle
local MAX   = 32    -- drones handled in one pass; the rest wait for the next
-- Tiles searched round an abandoned drone for what it was holding. It is wide
-- because a load a drone picked up by hand may still be lying where the drone
-- found it rather than travelling with it, and a pad lets its drone go thirty
-- tiles out.
local REACH = 40
local NONE  = -1

local DISPATCH    = 3     -- seconds between hand-outs while any body is remembered
local WHOLE_MAP   = 2000  -- tiles; wider than any map

local SCAN_KIND     = "Light"   -- what the map is searched round
local CELL          = 24        -- tiles; the side of a square of the map
local SCAN_REACH    = 22        -- tiles searched round a point: its square and a little over
local TOP_UP        = 0.8       -- a light further than this share of the reach from every point becomes one
local SCAN_EVERY    = 2.5       -- seconds between points
local ANCHORS_EVERY = 1800      -- seconds between fresh looks for the lights
local LISTS_EVERY   = 60        -- seconds the pads and slabs are kept before they are looked for again
local MIN_CHARGE  = 50    -- a drone flatter than this is not sent across the prison
local SHUNNED_FOR = 120   -- seconds a body a drone could not get to is left alone

-- The Predators' watch. A Predator goes after a prisoner it has just seen
-- caught in misconduct, and a search for prisoners hands back a full record of
-- every one in reach. A pad looking over its own ground every few seconds cost
-- more than the rest of the mod put together once a few Predators stood side
-- by side, each searching the same prisoners. So pads standing together share
-- one look here, and each is told the prisoner to go after, as TargetI,
-- TargetX and TargetY, and one to patrol towards, as RoamI, RoamX and RoamY.
local WATCH_EVERY       = 4     -- seconds between looks, as often as a pad looked for itself
local WORK_RANGE        = 30    -- tiles; a pad's own ground, as the pad has it
local SHARE_WITHIN      = 12    -- tiles; pads this near the first of a group share its look
local STRIKE_CEILING    = 0.8   -- a prisoner hurt this much is not gone after again
local MISCONDUCT_WINDOW = 45    -- seconds a prisoner stays a target after misconduct

-- What the game writes down when a prisoner does something it counts against
-- them.
local MISCONDUCT = {
    "TimeOfLastMisconduct", "TimeOfLastMisconductStaffAssault",
    "TimeOfLastMisconductPrisonerAssault", "TimeOfLastMisconductMurders",
    "TimeOfLastMisconductEscapeAttempt", "TimeOfLastMisconductSeriousInjury",
}

-- Every kind of person a hauler will lift the corpse of, prisoners first.
local BODY_KINDS = {
    "Prisoner", "Guard", "ArmedGuard", "RiotGuard", "Sniper", "DogHandler",
    "Workman", "Foreman", "Cook", "Janitor", "Gardener", "Doctor", "Orderly",
    "Paramedic", "Warden", "Chief", "Visitor", "Dog",
}

-- What a hauler can be holding. The only reason this script needs it is to be
-- able to put a load down: a body left in the arms of a drone that is about
-- to go would be in nobody's arms at all, and the game would never find it
-- again.
local LOADS = { "Garbage" }
for _, kind in ipairs(BODY_KINDS) do LOADS[#LOADS + 1] = kind end

local timer         = 0
local dispatchTimer = 0
local scanTimer     = 0
local clock         = 0
local anchors       = {}   -- { obj, x, y }: the lights searched round, in turn
local anchorAt      = 0
local anchorsAge    = ANCHORS_EVERY
local pass          = 0    -- whole passes of the map so far; picks the other kind searched
local pads          = {}   -- every Drone Charger, kept between hand-outs
local slabs         = {}   -- { obj, x, y }: every morgue slab, kept between hand-outs
local slabAt        = {}   -- slab id -> slab, for the same slabs
local listsAge      = LISTS_EVERY
local loose         = {}   -- body id -> { u, typ, x, y }: the dead seen lying where nobody holds them
local shunned       = {}   -- body id -> the clock until which it is not handed out
local watchTimer    = 0
local record        = {}   -- prisoner id -> their misconduct record when last looked at
local hot           = {}   -- prisoner id -> when a look saw that record move
local safe = pcall or function(f, ...) return true, f(...) end

local function num(v, fallback)
    return tonumber(v) or fallback
end

-- Puts down whatever the drone is holding. The load is standing where the
-- drone is, so the search is a short one, and it only runs for a drone that
-- has something in its slot, which is rare.
local function unload(drone)
    local held = num(Get(drone, "Slot0.i"), NONE)
    if held == NONE or drone.Id == nil then return end
    local mine = drone.Id.i
    for _, kind in ipairs(LOADS) do
        for obj in pairs(Find(drone, kind, REACH) or {}) do
            local id = obj.Id
            if id and id.i == held and num(Get(obj, "CarrierId.i"), NONE) == mine then
                Set(obj, "Loaded", false)
                Set(obj, "CarrierId.i", NONE)
                Set(obj, "CarrierId.u", NONE)
                Set(drone, "Slot0.i", NONE)
                Set(drone, "Slot0.u", NONE)
                return
            end
        end
    end
    Set(drone, "Slot0.i", NONE)
    Set(drone, "Slot0.u", NONE)
end

-- Every drone called SPENT has gone a whole sweep without its pad claiming
-- it. Each is renamed before it is removed, so a removal the game does not
-- carry out cannot hand the same drone back and spin this loop.
local function collect()
    for _ = 1, MAX do
        local drone = Game.GetObject(SPENT)
        if drone == nil then return end
        Set(drone, "Name", "")
        unload(drone)
        drone.Delete()
    end
end

-- Takes the mark off every drone that carries one. A pad puts its own back on
-- the next second.
local function expire()
    for _ = 1, MAX do
        local drone = Game.GetObject(MARK)
        if drone == nil then return end
        Set(drone, "Name", SPENT)
    end
end

-------------------------------------------------------------------------------
-- Handing out the dead
-------------------------------------------------------------------------------

-- A body is a person whose Damage has reached 1. That is the only test: the
-- game hands a script a DeathType for the living as well as the dead, so
-- reading one says nothing about whether anybody has died.
local function isCorpse(obj)
    return num(obj.Damage, 0) >= 1
end

-- The points to search round: the light nearest the middle of each square of
-- the map that has one, and any light left further than TOP_UP of the reach
-- from all of those. A light is chosen rather than any other object because a
-- prison lights every room and yard its people go in.
local function chooseAnchors(from)
    local cells, lights = {}, {}
    for light in pairs(Find(from, SCAN_KIND, WHOLE_MAP) or {}) do
        local pos = light.Pos
        local x, y = pos and num(pos.x, nil), pos and num(pos.y, nil)
        if x ~= nil and y ~= nil then
            local entry = { obj = light, x = x, y = y }
            lights[#lights + 1] = entry
            local cx, cy = math.floor(x / CELL), math.floor(y / CELL)
            local key = cx * 4096 + cy
            local dx, dy = x - (cx + 0.5) * CELL, y - (cy + 0.5) * CELL
            local d = dx * dx + dy * dy
            if cells[key] == nil or d < cells[key].d then
                cells[key] = { obj = light, x = x, y = y, d = d }
            end
        end
    end
    local chosen = {}
    for _, cell in pairs(cells) do chosen[#chosen + 1] = cell end
    local gap = (TOP_UP * SCAN_REACH) * (TOP_UP * SCAN_REACH)
    for _, light in ipairs(lights) do
        local covered = false
        for _, point in ipairs(chosen) do
            local dx, dy = light.x - point.x, light.y - point.y
            if dx * dx + dy * dy <= gap then covered = true break end
        end
        if not covered then chosen[#chosen + 1] = light end
    end
    anchors = chosen
    anchorAt = 0
end

-- Lets somebody alive up off a morgue slab. A slab holds whoever lies on it
-- the way a carrier does, so anybody alive who was put on one cannot move
-- until something lets go, and a slab holds only the dead by rights. Only a
-- slab's hold is broken: the living are carried by other things for good
-- reasons, a dog in its crate among them.
local function letUp(obj, id)
    local carrier = obj.CarrierId
    local slab = carrier and slabAt[num(carrier.i, NONE)]
    if slab == nil then return end
    Set(obj, "Loaded", false)
    Set(obj, "CarrierId.i", NONE)
    Set(obj, "CarrierId.u", NONE)
    if num(Get(slab, "Slot0.i"), NONE) == id.i then
        Set(slab, "Slot0.i", NONE)
        Set(slab, "Slot0.u", NONE)
    end
end

-- Every body of one kind lying round one point where nobody holds it. What
-- was remembered of that kind round that point and is not lying there now
-- has been picked up, and is forgotten. Anybody alive the search turns up
-- held down on a slab is let up on the way.
local function lookAround(point, kind)
    local seen = {}
    for obj in pairs(Find(point.obj, kind, SCAN_REACH) or {}) do
        local id = obj.Id
        if id and obj.Loaded ~= true and isCorpse(obj) then
            local pos = obj.Pos
            loose[id.i] = { u = id.u, typ = kind, x = num(pos.x, 0), y = num(pos.y, 0) }
            seen[id.i] = true
        elseif id and obj.Loaded == true and not isCorpse(obj) then
            letUp(obj, id)
        end
    end
    local reach = SCAN_REACH * SCAN_REACH
    for i, body in pairs(loose) do
        if body.typ == kind and not seen[i] then
            local dx, dy = body.x - point.x, body.y - point.y
            if dx * dx + dy * dy <= reach then loose[i] = nil end
        end
    end
end

local function scanNext()
    if #anchors == 0 or anchorsAge >= ANCHORS_EVERY then
        local from = Game.GetObject(PAD_MARK)
        if from == nil then return end
        anchorsAge = 0
        chooseAnchors(from)
        if #anchors == 0 then return end
    end
    anchorAt = anchorAt + 1
    if anchorAt > #anchors then
        anchorAt = 1
        pass = pass + 1
    end
    local point = anchors[anchorAt]
    local other = BODY_KINDS[2 + pass % (#BODY_KINDS - 1)]
    local ok = safe(function()
        lookAround(point, "Prisoner")
        lookAround(point, other)
    end)
    if not ok then
        -- the light has been taken down; the next fresh look finds the rest
        table.remove(anchors, anchorAt)
        anchorAt = anchorAt - 1
    end
end

local function refreshLists(anchor)
    pads, slabs, slabAt = {}, {}, {}
    for pad in pairs(Find(anchor, "DroneCharger", WHOLE_MAP) or {}) do
        pads[#pads + 1] = pad
    end
    for each in pairs(Find(anchor, "MorgueSlab", WHOLE_MAP) or {}) do
        local pos = each.Pos
        slabs[#slabs + 1] = { obj = each, x = num(pos.x, 0), y = num(pos.y, 0) }
        local id = each.Id
        if id then slabAt[id.i] = each end
    end
    listsAge = 0
end

-- The pads and slabs, looked for again once they are a minute old. Returns
-- false when there is no pad to search from.
local function freshLists()
    if listsAge < LISTS_EVERY and #pads > 0 then return true end
    local anchor = Game.GetObject(PAD_MARK)
    if anchor == nil then return false end
    refreshLists(anchor)
    return true
end

local function nearestTo(list, x, y, usable)
    local best, bestAt, near = nil, nil, nil
    for at, entry in pairs(list) do
        if usable(at, entry) then
            local dx, dy = entry.x - x, entry.y - y
            local d = dx * dx + dy * dy
            if near == nil or d < near then best, bestAt, near = entry, at, d end
        end
    end
    return best, bestAt
end

-- Hands each Hauler free to fly the remembered body nearest its pad, and the
-- free slab nearest that body to take it to. A slab already promised to a
-- drone is not promised again, so no more bodies go out than there are slabs
-- to take them.
local function handOut()
    local idle, taken, promised = {}, {}, {}
    for _, pad in ipairs(pads) do
        local failed = num(Get(pad, "BodyFail"), NONE)
        if failed ~= NONE then
            shunned[failed] = clock + SHUNNED_FOR
            Set(pad, "BodyFail", NONE)
        end
        if Get(pad, "Role") ~= "Predator" then
            local held = num(Get(pad, "BodyI"), NONE)
            local load = Get(pad, "LoadKind") or ""
            local slabI = num(Get(pad, "SlabI"), NONE)
            if slabI ~= NONE and (held ~= NONE or load == "Body") then promised[slabI] = true end
            if held ~= NONE then
                taken[held] = true
            elseif load == "" and num(Get(pad, "DroneI"), NONE) ~= NONE
                   and num(Get(pad, "Charge"), 0) >= MIN_CHARGE then
                idle[#idle + 1] = pad
            end
        end
    end
    if #idle == 0 then return end

    local free = {}
    for _, entry in ipairs(slabs) do
        local id = entry.obj.Id
        if id and not promised[id.i] and num(Get(entry.obj, "Slot0.i"), NONE) == NONE then
            free[#free + 1] = entry
        end
    end

    for _, pad in ipairs(idle) do
        if next(free) == nil then return end
        local px, py = num(pad.Pos.x, 0), num(pad.Pos.y, 0)
        local body, bodyI = nearestTo(loose, px, py, function(i)
            return not taken[i] and (shunned[i] or 0) <= clock
        end)
        if body == nil then return end
        local slab, slabAt = nearestTo(free, body.x, body.y, function() return true end)
        Set(pad, "BodyI", bodyI)
        Set(pad, "BodyU", body.u)
        Set(pad, "BodyType", body.typ)
        Set(pad, "BodyX", body.x)
        Set(pad, "BodyY", body.y)
        Set(pad, "SlabI", slab.obj.Id.i)
        Set(pad, "SlabX", slab.x)
        Set(pad, "SlabY", slab.y)
        taken[bodyI] = true
        loose[bodyI] = nil
        free[slabAt] = nil
    end
end

-- Nothing is searched at all while no body is remembered, and the pads and
-- slabs are only looked for again once a minute.
local function dispatch()
    if next(loose) == nil then return end
    if not freshLists() then return end
    if not safe(handOut) then
        listsAge = LISTS_EVERY     -- a pad or slab taken down since the last look
    end
end

-------------------------------------------------------------------------------
-- The Predators' watch
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
-- time a look saw that prisoner is misconduct that has just happened, whatever
-- either clock says.
--
-- A prisoner seen for the first time only sets the mark to measure the next
-- look against. That is what stops the Predators going after everybody with a
-- history the moment the game is loaded.
local function watch()
    local predators = {}
    for _, pad in ipairs(pads) do
        if Get(pad, "Role") == "Predator" then
            local pos = pad.Pos
            local x, y = pos and num(pos.x, nil), pos and num(pos.y, nil)
            if x ~= nil and y ~= nil then predators[#predators + 1] = { pad = pad, x = x, y = y } end
        end
    end
    if #predators == 0 then
        record, hot = {}, {}
        return
    end

    -- Every prisoner in any Predator's ground: one search for each group of
    -- pads standing together, made from the pad nearest the middle of the
    -- group and reaching the ground of the one furthest from it.
    local seen, fresh, grouped = {}, {}, {}
    for n, first in ipairs(predators) do
        if not grouped[n] then
            local group, cx, cy = {}, 0, 0
            for m = n, #predators do
                local other = predators[m]
                local dx, dy = other.x - first.x, other.y - first.y
                if not grouped[m] and dx * dx + dy * dy <= SHARE_WITHIN * SHARE_WITHIN then
                    grouped[m] = true
                    group[#group + 1] = other
                    cx, cy = cx + other.x, cy + other.y
                end
            end
            cx, cy = cx / #group, cy / #group
            local middle, near = nil, nil
            for _, p in ipairs(group) do
                local dx, dy = p.x - cx, p.y - cy
                local d = dx * dx + dy * dy
                if near == nil or d < near then middle, near = p, d end
            end
            local spread = 0
            for _, p in ipairs(group) do
                local dx, dy = p.x - middle.x, p.y - middle.y
                local d = math.sqrt(dx * dx + dy * dy)
                if d > spread then spread = d end
            end
            for obj in pairs(Find(middle.pad, "Prisoner", WORK_RANGE + spread) or {}) do
                local id = obj.Id
                if id and fresh[id.i] == nil then
                    local latest = lastCaught(obj)
                    fresh[id.i] = latest
                    if record[id.i] ~= nil and latest > record[id.i] then hot[id.i] = clock end
                    local pos = obj.Pos
                    seen[#seen + 1] = {
                        i = id.i, x = num(pos.x, 0), y = num(pos.y, 0),
                        open = hot[id.i] ~= nil and num(obj.Damage, 0) < STRIKE_CEILING and not isCorpse(obj),
                    }
                end
            end
        end
    end
    record = fresh
    for i, since in pairs(hot) do
        if clock - since > MISCONDUCT_WINDOW then hot[i] = nil end
    end

    -- Each pad is set on the nearest prisoner in its own ground caught in
    -- misconduct, and given any prisoner in its ground at random to patrol to.
    local reach = WORK_RANGE * WORK_RANGE
    for _, p in ipairs(predators) do
        local best, near, pick, count = nil, nil, nil, 0
        for _, one in ipairs(seen) do
            local dx, dy = one.x - p.x, one.y - p.y
            local d = dx * dx + dy * dy
            if d <= reach then
                count = count + 1
                if math.random(count) == 1 then pick = one end
                if one.open and (near == nil or d < near) then best, near = one, d end
            end
        end
        if best ~= nil then
            Set(p.pad, "TargetX", best.x)
            Set(p.pad, "TargetY", best.y)
            Set(p.pad, "TargetI", best.i)
        else
            Set(p.pad, "TargetI", NONE)
        end
        if pick ~= nil then
            Set(p.pad, "RoamX", pick.x)
            Set(p.pad, "RoamY", pick.y)
            Set(p.pad, "RoamI", pick.i)
        else
            Set(p.pad, "RoamI", NONE)
        end
    end
end

function Init()
end

function Update(timePassed)
    local dt = tonumber(timePassed) or 0
    clock = clock + dt
    timer = timer + dt
    scanTimer = scanTimer + dt
    dispatchTimer = dispatchTimer + dt
    watchTimer = watchTimer + dt
    anchorsAge = anchorsAge + dt
    listsAge = listsAge + dt
    if scanTimer >= SCAN_EVERY then
        scanTimer = 0
        -- the slabs are known before a look, so the living on one can be let up
        if freshLists() then scanNext() end
    end
    if dispatchTimer >= DISPATCH then
        dispatchTimer = 0
        dispatch()
    end
    if watchTimer >= WATCH_EVERY then
        watchTimer = 0
        if freshLists() then safe(watch) end
    end
    if timer < SWEEP then return end
    timer = 0
    collect()
    expire()
end

-- The game hands a script every object a search finds as a global named for
-- the object's type and id, and never takes one back, so a script that
-- searches holds on to everyone it has ever found. Every FORGET_EVERY seconds
-- those globals are cleared, and Lua's own collector frees what they held.
-- The lights this script searches round, and the pads and slabs, are kept
-- from one pass to the next, and reading one goes through its global, so
-- theirs are kept too.
local FORGET_EVERY = 20
local forgetTimer = 0
local runUpdate = Update
function Update(timePassed)
    forgetTimer = forgetTimer + (tonumber(timePassed) or 0)
    if forgetTimer >= FORGET_EVERY then
        forgetTimer = 0
        if _G ~= nil then
            for name, value in pairs(_G) do
                if type(value) == "table" and type(name) == "string" and name:find("i%-?%d+u%-?%d+$")
                    and not name:find("^" .. SCAN_KIND) and not name:find("^DroneCharger")
                    and not name:find("^MorgueSlab") then
                    _G[name] = nil
                end
            end
        end
    end
    return runUpdate(timePassed)
end
