-- The Robot Uplink services the robot staff. How the mod defines staff and
-- the settings it ships are what stop a robot tiring, needing anything or
-- being corrupted; the uplink is the backstop for a robot that was already
-- tired, damaged or crooked when the mod was switched on, and for anything
-- that slips past those settings. It recharges every kind of robot, and it
-- repairs the ones that guard and wipes a corrupted one clean.
--
-- A search of the map is the dearest thing a script can ask the game for, so
-- the uplink looks at one kind of robot a round and reads a few things from
-- each, and writes only to a robot that needs it.

local Find = Object.GetNearbyObjects
local Set = Object.SetProperty

-- Every kind of robot, and which of them guard. All of them are recharged;
-- the guards are also repaired and wiped clean.
local KINDS = { "Guard", "ArmedGuard", "DogHandler", "Sniper", "Workman", "Foreman", "Cook", "Janitor", "Gardener",
                "Farmer", "Doctor", "Orderly", "Psychiatrist", "Psychologist", "Warden", "Chief", "Accountant",
                "Lawyer" }
local GUARDS = { Guard = true, ArmedGuard = true, DogHandler = true }
local WHOLE_MAP = 5000
local ROUND = 3                 -- seconds between looks, one kind a look
local LOW_CHARGE = 70           -- a robot under this is topped up
local FULL_CHARGE = 100

local roundTimer = math.random() * ROUND
local turn = 0
local online = {}               -- kind -> robots seen on the last look
local shown = ""

local function service(kind)
    local n = 0
    for robot in pairs(Find(kind, WHOLE_MAP) or {}) do
        if (tonumber(robot.Damage) or 0) < 1 then n = n + 1 end     -- a wreck is not online
        local charge = tonumber(robot.Energy)
        if charge and charge < LOW_CHARGE then Set(robot, "Energy", FULL_CHARGE) end
        if GUARDS[kind] then
            if robot.Corrupted == true then Set(robot, "Corrupted", false) end
            local damage = tonumber(robot.Damage) or 0
            if damage > 0 and damage < 1 then Set(robot, "Damage", 0) end
        end
    end
    online[kind] = n
end

function Update(timePassed)
    roundTimer = roundTimer + (tonumber(timePassed) or 0)
    if roundTimer < ROUND then return end
    roundTimer = 0
    turn = turn % #KINDS + 1
    service(KINDS[turn])
    local total = 0
    for _, n in pairs(online) do total = total + n end
    if tostring(total) ~= shown then
        shown = tostring(total)
        this.Tooltip = { "tooltip_RobotUplink", total, "X" }
    end
end

-- The game hands a script every object a search finds as a global named for
-- the object's type and id, and never takes one back, so a script that
-- searches holds on to everyone it has ever found. Every FORGET_EVERY seconds
-- those globals are cleared, and Lua's own collector frees what they held.
-- Reading a property of an object goes through its global, so this is only
-- for a script that keeps no object from one update to the next.
local FORGET_EVERY = 20
local forgetTimer = math.random() * FORGET_EVERY
local runUpdate = Update
function Update(timePassed)
    forgetTimer = forgetTimer + timePassed
    if forgetTimer >= FORGET_EVERY then
        forgetTimer = 0
        if _G ~= nil then
            for name, value in pairs(_G) do
                if type(value) == "table" and type(name) == "string" and name:find("i%-?%d+u%-?%d+$") then
                    _G[name] = nil
                end
            end
        end
    end
    return runUpdate(timePassed)
end
