-- Robot Staff: the mod's world script. It removes drones whose pad has gone.
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

local Get  = Object.GetProperty
local Set  = Object.SetProperty
local Find = Object.GetNearbyObjects

local MARK  = "RobotDroneUnit"    -- a pad's mark on the drone it owns
local SPENT = "RobotDroneUnit2"   -- the mark taken off, one sweep from removal

local SWEEP = 15    -- seconds between sweeps; fifteen times the pad's own cycle
local MAX   = 32    -- drones handled in one pass; the rest wait for the next
-- Tiles searched round an abandoned drone for what it was holding. It is wide
-- because a load a drone picked up by hand may still be lying where the drone
-- found it rather than travelling with it, and a pad lets its drone go thirty
-- tiles out.
local REACH = 40
local NONE  = -1

-- What a hauler can be holding. It is the drone's own list, and the only
-- reason this script knows it is to be able to put a load down: a body left
-- in the arms of a drone that is about to go would be in nobody's arms at
-- all, and the game would never find it again.
local LOADS = {
    "Prisoner", "Guard", "ArmedGuard", "RiotGuard", "Sniper", "DogHandler",
    "Workman", "Foreman", "Cook", "Janitor", "Gardener", "Doctor", "Orderly",
    "Paramedic", "Warden", "Chief", "Visitor", "Dog", "Garbage",
}

local timer = 0

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

function Init()
end

function Update(timePassed)
    timer = timer + (tonumber(timePassed) or 0)
    if timer < SWEEP then return end
    timer = 0
    collect()
    expire()
end
