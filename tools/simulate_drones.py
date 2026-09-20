"""Runs data/scripts/DroneCharger.lua and data/world.lua against a stand-in for
the game and checks what the drones do with it.

The stand-in is the part of the game the two scripts actually touch: objects
with the fields the game keeps on them, a search that answers by type and
distance, spawning, deleting, a clock, and a pathfinder that walks an object
towards wherever it was last sent. Both scripts are loaded into environments of
their own, so the pad's Update and the world script's Update do not collide the
way they would as plain globals.

Usage: python simulate_drones.py      (needs lupa)
"""

import math
import os
import sys

from lupa import LuaRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "RobotDroneUnit"
SPENT = "RobotDroneUnit2"
SPEED = 4.0          # tiles a second, standing in for the game's own pathing
STEP = 0.5           # seconds a tick


class World:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("math.randomseed(1)")
        self.objects = []
        self.next_id = 100
        self.clock = 1000.0
        self.searches = 0
        self.navigations = 0
        self.sounds = 0
        self.buttons = {}

    # ---------------------------------------------------------------- objects

    def make(self, kind, x, y, **fields):
        self.next_id += 1
        obj = self.lua.eval("{}")
        obj.Type = kind
        obj.Id = self.lua.table_from({"i": self.next_id, "u": self.next_id * 7})
        obj.Pos = self.lua.table_from({"x": float(x), "y": float(y)})
        obj.Dest = self.lua.table_from({"x": float(x), "y": float(y)})
        obj.Slot0 = self.lua.table_from({"i": -1, "u": -1})
        obj.CarrierId = self.lua.table_from({"i": -1, "u": -1})
        obj.Name = ""
        obj.SubType = 0
        for key, value in fields.items():
            obj[key] = value
        here = self
        obj.Delete = lambda: here.remove(obj)
        self.objects.append(obj)
        return obj

    def remove(self, obj):
        self.objects = [o for o in self.objects if o is not obj]

    def alive(self, obj):
        return any(o is obj for o in self.objects)

    def of_kind(self, kind):
        return [o for o in self.objects if o.Type == kind]

    # ------------------------------------------------------------------- API

    @staticmethod
    def _walk(obj, path):
        parts = path.split(".")
        for part in parts[:-1]:
            obj = obj[part]
            if obj is None:
                return None, None
        return obj, parts[-1]

    def get(self, obj, path):
        holder, leaf = self._walk(obj, path)
        return None if holder is None else holder[leaf]

    def put(self, obj, path, value):
        holder, leaf = self._walk(obj, path)
        if holder is not None:
            holder[leaf] = value

    def find(self, anchor, kind, reach):
        self.searches += 1
        reach = float(reach)
        out = self.lua.eval("{}")
        for obj in self.of_kind(kind):
            gap = math.hypot(obj.Pos.x - anchor.Pos.x, obj.Pos.y - anchor.Pos.y)
            if gap <= reach:
                out[obj] = str(gap)
        return out

    def spawn(self, kind, x, y):
        return self.make(kind, x, y)

    def navigate(self, obj, x, y):
        self.navigations += 1
        obj.Dest.x, obj.Dest.y = float(x), float(y)

    def named(self, name):
        for obj in self.objects:
            if obj.Name == name:
                return obj
        return None

    # ------------------------------------------------------------------ time

    def tick(self, seconds=STEP):
        self.clock += seconds
        for obj in list(self.objects):
            gap = math.hypot(obj.Dest.x - obj.Pos.x, obj.Dest.y - obj.Pos.y)
            if gap > 0.01:
                step = min(gap, SPEED * seconds)
                obj.Pos.x += (obj.Dest.x - obj.Pos.x) * step / gap
                obj.Pos.y += (obj.Dest.y - obj.Pos.y) * step / gap


def load(world, path, this):
    """Loads one of the mod's scripts into an environment of its own."""
    env = world.lua.eval("{}")
    env.this = this
    world.lua.globals().Object = world.lua.table_from({
        "GetProperty": world.lua.eval("""function(get, this) return function(a, b)
            if b == nil then return get(this, a) else return get(a, b) end end end""")(world.get, this),
        "SetProperty": world.lua.eval("""function(put, this) return function(a, b, c)
            if c == nil then put(this, a, b) else put(a, b, c) end end end""")(world.put, this),
        "GetNearbyObjects": world.lua.eval("""function(find, this) return function(a, b, c)
            if c == nil then return find(this, a, b) else return find(a, b, c) end end end""")(world.find, this),
        "NavigateTo": world.lua.eval("""function(nav, this) return function(a, b, c)
            if c == nil then nav(this, a, b) else nav(a, b, c) end end end""")(world.navigate, this),
        "Spawn": world.spawn,
        "Sound": lambda *a: world.__setattr__("sounds", world.sounds + 1),
        "Delete": lambda obj: world.remove(obj),
    })
    world.lua.globals().Game = world.lua.table_from({
        "Time": lambda: str(world.clock),
        "GetObject": world.named,
    })
    src = open(os.path.join(ROOT, path)).read()
    chunk = world.lua.eval("""function(src, name, env)
        setmetatable(env, { __index = _G })
        local f, e = load(src, name, "t", env)
        if not f then error(e) end
        f()
        return env
    end""")
    return chunk(src, path, env)


def pad_at(world, x, y):
    """A Drone Charger and the script that runs it, wired together."""
    this = world.make("DroneCharger", x, y)
    this.AddInterfaceComponent = lambda name, kind, caption: world.buttons.__setitem__(name, caption)
    this.RemoveInterfaceComponent = lambda name: world.buttons.pop(name, None)
    env = load(world, os.path.join("data", "scripts", "DroneCharger.lua"), this)
    env.Create()
    return this, env


def run(env, world, seconds, also=None):
    for _ in range(int(seconds / STEP)):
        env.Update(STEP)
        if also is not None:
            also.Update(STEP)
        world.tick()


def run_until(env, world, ready, seconds=90, also=None):
    """Ticks until the world says it is ready, so a test that wants to catch a
    drone mid-job does not depend on how fast the stand-in walks it."""
    for _ in range(int(seconds / STEP)):
        if ready():
            return True
        env.Update(STEP)
        if also is not None:
            also.Update(STEP)
        world.tick()
    return ready()


FAILURES = []


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILURES.append(what)


def corpse(world, kind, x, y):
    return world.make(kind, x, y, DeathType="Stabbed", Damage=1.0, Loaded=False)


# --------------------------------------------------------------------- tests

def test_builds_and_marks():
    w = World()
    this, env = pad_at(w, 20, 20)
    run(env, w, 3)
    made = w.of_kind("HaulerDrone")
    check("a new pad builds exactly one Hauler", len(made) == 1)
    check("the pad marks its drone", made and made[0].Name == MARK)
    check("the pad remembers its drone's id", this.DroneI == made[0].Id.i)
    check("the pad offers a model button", "DroneRole" in w.buttons)
    check("a Hauler pad offers no duty button", "DroneDuty" not in w.buttons)
    run(env, w, 20)
    check("it never builds a second drone", len(w.of_kind("HaulerDrone")) == 1)


def test_hauls_a_body_to_a_slab():
    w = World()
    this, env = pad_at(w, 20, 20)
    slab = w.make("MorgueSlab", 14, 20)
    body = corpse(w, "Prisoner", 28, 22)
    run(env, w, 60)
    drone = w.of_kind("HaulerDrone")[0]
    check("the body ends up on the slab", slab.Slot0.i == body.Id.i)
    check("the slab is the body's carrier", body.CarrierId.i == slab.Id.i)
    check("the drone is empty again", drone.Slot0.i == -1)
    check("the body was never deleted", w.alive(body))


def test_leaves_a_body_somebody_else_holds():
    w = World()
    this, env = pad_at(w, 20, 20)
    w.make("MorgueSlab", 18, 20)
    guard = w.make("Guard", 26, 20)
    body = corpse(w, "Prisoner", 26, 20)
    body.Loaded = True
    body.CarrierId.i, body.CarrierId.u = guard.Id.i, guard.Id.u
    run(env, w, 40)
    check("a body in a guard's arms is left alone", body.CarrierId.i == guard.Id.i)


def test_will_not_lift_without_a_free_slab():
    w = World()
    this, env = pad_at(w, 20, 20)
    taken = w.make("MorgueSlab", 18, 20)
    taken.Slot0.i, taken.Slot0.u = 1, 1
    body = corpse(w, "Prisoner", 26, 20)
    run(env, w, 40)
    drone = w.of_kind("HaulerDrone")[0]
    check("with every slab taken no body is picked up",
          drone.Slot0.i == -1 and body.Loaded is not True)


def test_clears_rubbish_to_the_pad():
    w = World()
    this, env = pad_at(w, 20, 20)
    bag = w.make("Garbage", 27, 24, Loaded=False)
    run(env, w, 60)
    check("rubbish is taken back to the pad and broken down", not w.alive(bag))
    check("the drone is empty afterwards", w.of_kind("HaulerDrone")[0].Slot0.i == -1)


def test_bodies_come_before_rubbish():
    w = World()
    this, env = pad_at(w, 20, 20)
    slab = w.make("MorgueSlab", 20, 16)
    body = corpse(w, "Prisoner", 24, 20)
    bag = w.make("Garbage", 21, 20, Loaded=False)
    order = []
    for _ in range(120):
        env.Update(STEP)
        w.tick()
        if slab.Slot0.i == body.Id.i and "body" not in order:
            order.append("body")
        if not w.alive(bag) and "bag" not in order:
            order.append("bag")
    check("the body reaches the morgue before the nearer rubbish is touched",
          order[:1] == ["body"])
    check("the rubbish is cleared afterwards", order == ["body", "bag"])


def test_a_stolen_load_is_let_go_of():
    w = World()
    this, env = pad_at(w, 20, 20)
    w.make("MorgueSlab", 45, 20)     # far enough that the delivery is still running
    body = corpse(w, "Prisoner", 24, 20)
    lifted = run_until(env, w, lambda: any(d.Slot0.i == body.Id.i for d in w.of_kind("HaulerDrone")))
    drone = w.of_kind("HaulerDrone")[0]
    check("the drone picked the body up", lifted)
    thief = w.make("Guard", 24, 20)
    body.CarrierId.i, body.CarrierId.u = thief.Id.i, thief.Id.u
    run(env, w, 4)
    check("a load taken by somebody else leaves the drone empty", drone.Slot0.i == -1)


def test_never_flies_past_its_range():
    w = World()
    this, env = pad_at(w, 20, 20)
    corpse(w, "Prisoner", 120, 20)   # well outside the pad's reach
    run(env, w, 60)
    drone = w.of_kind("HaulerDrone")[0]
    gap = math.hypot(drone.Pos.x - 20, drone.Pos.y - 20)
    check("a drone is never sent beyond its pad's reach", gap <= 31)


def test_charge_sends_it_home():
    w = World()
    this, env = pad_at(w, 20, 20)
    run(env, w, 3)
    this.Charge = 26.0
    corpse(w, "Prisoner", 40, 20)    # work it would otherwise fly off to
    w.make("MorgueSlab", 42, 20)
    run(env, w, 40)
    drone = w.of_kind("HaulerDrone")[0]
    home = math.hypot(drone.Pos.x - 20, drone.Pos.y - 20) <= 1.5
    check("a flat drone comes home instead of taking work", home)
    check("and charges back up on the pad", float(this.Charge) > 60)


def test_predator_shocks_only_the_guilty():
    w = World()
    this, env = pad_at(w, 20, 20)
    env.ButtonPressed_DroneRole()
    clean = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    guilty = w.make("Prisoner", 26, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    run(env, w, 12)                 # long enough for the pad to take its marks
    check("a prisoner with an old record is not attacked for it",
          float(guilty.Damage) == 0 and float(clean.Damage) == 0)
    guilty.TimeOfLastMisconductPrisonerAssault = 1234.0    # misconduct, right now
    run(env, w, 60)
    check("a prisoner whose record has just moved is shocked", float(guilty.Damage) > 0)
    check("a prisoner whose record has not moved is left be", float(clean.Damage) == 0)
    check("the shock stops short of killing", float(guilty.Damage) <= 0.8)
    check("the pad offers a duty button for a Predator", "DroneDuty" in w.buttons)


def test_predator_reads_no_clock():
    """The records are written on the prison's clock and Game.Time answers with
    how long the game has been running, so the pad must never subtract one from
    the other. A record far outside the pad's own clock still has to work."""
    w = World()
    this, env = pad_at(w, 20, 20)
    env.ButtonPressed_DroneRole()
    old = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=500000.0)
    run(env, w, 12)
    check("a record from far outside this clock is not attacked on sight",
          float(old.Damage) == 0)
    old.TimeOfLastMisconduct = 500010.0
    run(env, w, 60)
    check("and is shocked once that record moves", float(old.Damage) > 0)


def test_predator_lets_a_prisoner_go():
    w = World()
    this, env = pad_at(w, 20, 20)
    env.ButtonPressed_DroneRole()
    one = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    run(env, w, 12)
    one.TimeOfLastMisconduct = 950.0
    run(env, w, 30)
    check("the shocking starts", float(one.Damage) > 0)
    run(env, w, 60)                 # well past the window the record opened
    settled = float(one.Damage)
    run(env, w, 150)
    check("and stops once the misconduct is old news", float(one.Damage) == settled)
    check("the prisoner is left alive", settled < 1.0)


def test_predator_holds_its_post():
    w = World()
    this, env = pad_at(w, 20, 20)
    env.ButtonPressed_DroneRole()
    env.ButtonPressed_DroneDuty()
    run(env, w, 60)
    drone = w.of_kind("PredatorDrone")[0]
    check("on Guard Post the drone stays beside its pad",
          math.hypot(drone.Pos.x - 20, drone.Pos.y - 20) <= 6)


def test_switching_model_scraps_the_old_drone():
    w = World()
    this, env = pad_at(w, 20, 20)
    w.make("MorgueSlab", 45, 20)
    body = corpse(w, "Prisoner", 24, 20)
    check("the hauler is carrying when the model is switched",
          run_until(env, w, lambda: any(d.Slot0.i == body.Id.i for d in w.of_kind("HaulerDrone"))))
    env.ButtonPressed_DroneRole()
    run(env, w, 6)
    check("the old drone is gone", not w.of_kind("HaulerDrone"))
    check("a Predator is built in its place", len(w.of_kind("PredatorDrone")) == 1)
    check("the body it was holding is put down, not lost",
          w.alive(body) and body.CarrierId.i == -1 and body.Loaded is False)


def test_world_script_clears_an_abandoned_drone():
    w = World()
    this, env = pad_at(w, 20, 20)
    world = load(w, os.path.join("data", "world.lua"), this)
    world.Init()
    run(env, w, 45, also=world)
    drone = w.of_kind("HaulerDrone")[0]
    check("a drone whose pad still stands is never swept through two sweeps", w.alive(drone))

    # something to be holding when the pad goes, and nowhere to put it down
    w.make("MorgueSlab", 45, 20)
    body = corpse(w, "Prisoner", 24, 20)
    carrying = run_until(env, w, lambda: drone.Slot0.i == body.Id.i, also=world)
    check("the drone is carrying before its pad goes", carrying)

    w.remove(this)                      # the pad is dismantled
    for _ in range(80):
        world.Update(STEP)
        w.tick()
    check("the abandoned drone is removed", not w.alive(drone))
    check("what it was carrying is put down rather than lost",
          w.alive(body) and body.CarrierId.i == -1 and body.Loaded is False)


def test_cost_stays_low():
    w = World()
    this, env = pad_at(w, 20, 20)
    w.make("MorgueSlab", 18, 20)
    for n in range(6):
        w.make("Prisoner", 22 + n, 22, Damage=0.0)
    run(env, w, 120)
    check("a quiet pad searches the map a handful of times a second",
          w.searches / 120 < 4, )
    check("a standing order is not repeated every tick", w.navigations < 120)


CASES = (test_builds_and_marks, test_hauls_a_body_to_a_slab,
         test_leaves_a_body_somebody_else_holds, test_will_not_lift_without_a_free_slab,
         test_clears_rubbish_to_the_pad, test_bodies_come_before_rubbish,
         test_a_stolen_load_is_let_go_of, test_never_flies_past_its_range,
         test_charge_sends_it_home, test_predator_shocks_only_the_guilty,
         test_predator_reads_no_clock, test_predator_lets_a_prisoner_go,
         test_predator_holds_its_post,
         test_switching_model_scraps_the_old_drone,
         test_world_script_clears_an_abandoned_drone, test_cost_stays_low)


def main():
    for case in CASES:
        print("\n" + case.__name__[5:].replace("_", " "))
        case()
    print("\nfailures:", len(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
