-- The Robot Uplink keeps the robot guards running. Guards, Armed Guards and
-- Dog Handlers never tire and are never corrupt because of how the mod defines
-- them and the settings it ships; the uplink is the backstop for a guard who
-- was already tired or already crooked when the mod was switched on, and for
-- anything that slips past those settings. It tops up a flagging robot's
-- charge and wipes a corrupted one clean.
--
-- A search of the map is the dearest thing a script can ask the game for, so
-- the uplink looks at one kind of guard a round and reads two things from
-- each, and writes only to a robot that needs it.

local Find = Object.GetNearbyObjects
local Set = Object.SetProperty

local KINDS = { "Guard", "ArmedGuard", "DogHandler" }
local WHOLE_MAP = 5000
local ROUND = 6                 -- seconds between looks, one kind a look
local LOW_CHARGE = 70           -- a robot under this is topped up
local FULL_CHARGE = 100

local roundTimer = math.random() * ROUND
local turn = 0
local online = {}               -- kind -> robots seen on the last look
local shown = ""

local function service(kind)
    local n = 0
    for robot in pairs(Find(kind, WHOLE_MAP) or {}) do
        n = n + 1
        local charge = tonumber(robot.Energy)
        if charge and charge < LOW_CHARGE then Set(robot, "Energy", FULL_CHARGE) end
        if robot.Corrupted == true then Set(robot, "Corrupted", false) end
    end
    online[kind] = n
end

function Update(timePassed)
    roundTimer = roundTimer + (tonumber(timePassed) or 0)
    if roundTimer < ROUND then return end
    roundTimer = 0
    turn = turn % #KINDS + 1
    service(KINDS[turn])
    local total = (online.Guard or 0) + (online.ArmedGuard or 0) + (online.DogHandler or 0)
    if tostring(total) ~= shown then
        shown = tostring(total)
        this.Tooltip = { "tooltip_RobotUplink", total, "X" }
    end
end
