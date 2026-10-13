"""Runs data/scripts/DroneCharger.lua and data/world.lua against a stand-in for
the game and checks what the drones do with it.

The stand-in is the part of the game the two scripts actually touch: objects
with the fields the game keeps on them, a search that answers by type and
distance, spawning, deleting, a clock, a pathfinder that walks an object
towards wherever it was last sent, and an object's interface: components put
on with Interface.AddComponent, captions written with SetInterfaceCaption, and
a press of a button calling <component name>Clicked on the script. Every
script is loaded into an environment of its own, with its own `this` behind
Object, so any number of pads and the world script run side by side the way
they do in the game.

A search's cost is counted as the records it hands back, because building a
script record for every object found is where the game spends the time.

Usage: python simulate_drones.py      (needs lupa)
"""

import math
import os
import sys

from lupa import LuaRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "RobotDroneUnit"
PAD_MARK = "RobotDronePad"
SPEED = 4.0          # tiles a second, standing in for the game's own pathing
STEP = 0.5           # seconds a tick

BODY_KINDS = ["Prisoner", "Guard", "ArmedGuard", "RiotGuard", "Sniper", "DogHandler",
              "Workman", "Foreman", "Cook", "Janitor", "Gardener", "Doctor", "Orderly",
              "Paramedic", "Warden", "Chief", "Visitor", "Dog"]


class World:
    def __init__(self, root=ROOT):
        self.root = root
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("math.randomseed(1)")
        self.objects = []
        self.next_id = 100
        self.clock = 1000.0
        self.searches = 0
        self.records = 0
        self.navigations = 0
        self.sounds = 0
        self.moving = set()
        self.walls = set()    # (x, y) of every tile nobody can be sent onto
        self.scripts = []     # every pad's environment, then the world script's
        self.world_env = None

    # ---------------------------------------------------------------- objects

    def make(self, kind, x, y, **fields):
        """An object as a script sees it. A person carries a DeathType whether
        or not they are dead, the way the game hands one to a script."""
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
        if kind in BODY_KINDS:
            obj.DeathType = 0
        for key, value in fields.items():
            obj[key] = value
        here = self
        obj.Delete = lambda: here.remove(obj)
        self.objects.append(obj)
        return obj

    def remove(self, obj):
        """Takes an object out of the world. A script still holding it reads
        its position as nothing from then on, the way the game hands back a
        position for an object that has been deleted."""
        self.objects = [o for o in self.objects if o is not obj]
        obj.Pos.x = None
        obj.Pos.y = None

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
                self.records += 1
        return out

    def spawn(self, kind, x, y):
        return self.make(kind, x, y)

    def navigate(self, obj, x, y):
        """Sends an object towards a point. A point on a wall tile has no
        route to it, and the object stays where it is."""
        self.navigations += 1
        self.moving.add(obj.Id.i)
        if (math.floor(x), math.floor(y)) in self.walls:
            obj.Dest.x, obj.Dest.y = obj.Pos.x, obj.Pos.y
            return
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
            if obj.Id.i not in self.moving:
                continue
            gap = math.hypot(obj.Dest.x - obj.Pos.x, obj.Dest.y - obj.Pos.y)
            if gap > 0.01:
                step = min(gap, SPEED * seconds)
                obj.Pos.x += (obj.Dest.x - obj.Pos.x) * step / gap
                obj.Pos.y += (obj.Dest.y - obj.Pos.y) * step / gap


def load(world, path, this):
    """Loads one of the mod's scripts into an environment of its own, with its
    own Object bound to its own `this`."""
    env = world.lua.eval("{}")
    env.this = this
    env.Object = world.lua.table_from({
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
    env.Game = world.lua.table_from({
        "Time": lambda: str(world.clock),
        "GetObject": world.named,
    })
    env.Interface = world.lua.table_from({
        "AddComponent": world.lua.eval("""function(obj, name, kind, caption)
            obj.Buttons = obj.Buttons or {}
            obj.Buttons[name] = caption
        end"""),
    })
    src = open(os.path.join(world.root, path)).read()
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
    this.SetInterfaceCaption = world.lua.eval("""function(this) return function(name, caption)
        this.Buttons = this.Buttons or {}
        this.Buttons[name] = caption
    end end""")(this)
    env = load(world, os.path.join("data", "scripts", "DroneCharger.lua"), this)
    env.Create()
    world.scripts.insert(0, env)
    return this, env


def with_world(world, area=(0, 0, 64, 64)):
    """The mod's world script, run alongside every pad, over a prison lit with
    a light every eight tiles across `area` (x0, y0, x1, y1): the world script
    searches the map round the lights."""
    x0, y0, x1, y1 = area
    for x in range(int(x0), int(x1) + 1, 8):
        for y in range(int(y0), int(y1) + 1, 8):
            world.make("Light", x + 0.5, y + 0.5)
    env = load(world, os.path.join("data", "world.lua"), world.lua.eval("{}"))
    env.Init()
    world.world_env = env
    world.scripts.append(env)
    return env


def press(world, this, env, name):
    """A press of a button the pad has put on."""
    buttons = this.Buttons
    if buttons is None or buttons[name] is None:
        raise AssertionError("no %s button on the pad" % name)
    env[name + "Clicked"]()


def run(world, seconds):
    for _ in range(int(seconds / STEP)):
        for env in world.scripts:
            env.Update(STEP)
        world.tick()


def run_until(world, ready, seconds=90):
    """Ticks until the world says it is ready, so a test that wants to catch a
    drone mid-job does not depend on how fast the stand-in walks it."""
    for _ in range(int(seconds / STEP)):
        if ready():
            return True
        for env in world.scripts:
            env.Update(STEP)
        world.tick()
    return ready()


FAILURES = []


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        FAILURES.append(what)


def corpse(world, kind, x, y):
    return world.make(kind, x, y, DeathType="Stabbed", Damage=1.0, Loaded=False)


def on_a_slab(world, body):
    return any(s.Slot0.i == body.Id.i for s in world.of_kind("MorgueSlab")) \
        and body.CarrierId.i in [s.Id.i for s in world.of_kind("MorgueSlab")]


# --------------------------------------------------------------------- tests

def test_builds_and_marks():
    w = World()
    this, env = pad_at(w, 20, 20)
    run(w, 3)
    made = w.of_kind("HaulerDrone")
    check("a new pad builds exactly one Hauler", len(made) == 1)
    check("the pad marks its drone", made and made[0].Name == MARK)
    check("the pad carries the name the world script searches from", this.Name == PAD_MARK)
    check("the pad remembers its drone's id", this.DroneI == made[0].Id.i)
    check("the pad puts its button on through Interface.AddComponent",
          this.Buttons is not None and this.Buttons["DroneMode"] == "button_DroneMode_Hauler")
    check("a press calls DroneModeClicked", callable(env.DroneModeClicked))
    run(w, 20)
    check("it never builds a second drone", len(w.of_kind("HaulerDrone")) == 1)


def test_the_button_walks_through_the_modes():
    w = World()
    this, env = pad_at(w, 20, 20)
    run(w, 3)
    press(w, this, env, "DroneMode")
    run(w, 3)
    check("one press makes a Predator on patrol",
          this.Role == "Predator" and this.Duty == "Patrol"
          and this.Buttons["DroneMode"] == "button_DroneMode_Patrol")
    check("the Hauler is scrapped and a Predator built",
          not w.of_kind("HaulerDrone") and len(w.of_kind("PredatorDrone")) == 1)
    predator = w.of_kind("PredatorDrone")[0]
    press(w, this, env, "DroneMode")
    run(w, 3)
    check("a second press puts it on Guard Post",
          this.Duty == "Post" and this.Buttons["DroneMode"] == "button_DroneMode_Post")
    check("changing duty keeps the same drone",
          w.of_kind("PredatorDrone") == [predator] and w.alive(predator))
    press(w, this, env, "DroneMode")
    run(w, 3)
    check("a third press brings back the Hauler",
          this.Role == "Hauler" and this.Buttons["DroneMode"] == "button_DroneMode_Hauler"
          and len(w.of_kind("HaulerDrone")) == 1 and not w.of_kind("PredatorDrone"))


def test_hauls_a_body_to_a_slab():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    slab = w.make("MorgueSlab", 14, 20)
    body = corpse(w, "Prisoner", 28, 22)
    run(w, 60)
    drone = w.of_kind("HaulerDrone")[0]
    check("the body ends up on the slab", slab.Slot0.i == body.Id.i)
    check("the slab is the body's carrier", body.CarrierId.i == slab.Id.i)
    check("the drone is empty again", drone.Slot0.i == -1)
    check("the body was never deleted", w.alive(body))
    check("the pad has nothing left handed to it", this.BodyI == -1)


def test_fetches_a_body_from_across_the_map():
    """The pad's own ground is thirty tiles. A body and a slab far outside it
    are still the Hauler's to move."""
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w, (0, 0, 160, 128))
    slab = w.make("MorgueSlab", 150, 120)
    body = corpse(w, "Prisoner", 150, 20)
    run(w, 400)
    check("a body a hundred tiles off reaches a slab a hundred tiles off", slab.Slot0.i == body.Id.i)
    drone = w.of_kind("HaulerDrone")[0]
    check("and the drone comes home afterwards",
          math.hypot(drone.Pos.x - 20, drone.Pos.y - 20) <= 1.5)


def test_finds_old_bodies_of_every_kind():
    """Only prisoners are searched on every look. Every other kind is
    searched in turn, and a body of any kind still has to be found and moved,
    however long it has been lying there."""
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w, (0, 0, 96, 72))
    for n in range(len(BODY_KINDS) + 2):
        w.make("MorgueSlab", 5, 5 + n)
    bodies = [corpse(w, kind, 40 + 3 * n, 60) for n, kind in enumerate(BODY_KINDS)]
    run(w, 2400)
    left = [b.Type for b in bodies if not on_a_slab(w, b)]
    check("a body of every kind is carried to a slab", not left)
    if left:
        print("     still lying:", left)


def test_pads_never_chase_the_same_body():
    w = World()
    pads = [pad_at(w, 20 + 3 * n, 20) for n in range(3)]
    with_world(w)
    for n in range(4):
        w.make("MorgueSlab", 10, 30 + n)
    bodies = [corpse(w, "Prisoner", 60 + 5 * n, 40) for n in range(3)]
    handed = []
    for _ in range(int(120 / STEP)):
        for env in w.scripts:
            env.Update(STEP)
        w.tick()
        held = [int(p.BodyI) for p, _ in pads if p.BodyI is not None and int(p.BodyI) != -1]
        if len(held) != len(set(held)):
            handed.append(held)
    check("no body is handed to two pads at once", not handed)
    check("three pads move three bodies", all(on_a_slab(w, b) for b in bodies))


def test_never_lifts_the_living():
    """The game hands a script a DeathType for the living too. Somebody alive
    is never a body, whatever it reads, and never reaches a slab."""
    w = World()
    pads = [pad_at(w, 20 + 3 * n, 20) for n in range(4)]
    with_world(w)
    for n in range(6):
        w.make("MorgueSlab", 10, 30 + n)
    living = []
    for n, kind in enumerate(BODY_KINDS):
        for death in (0, "Fight", "None", "Unknown"):
            living.append(w.make(kind, 30 + 2 * n, 40, DeathType=death, Damage=0.4))
    body = corpse(w, "Prisoner", 50, 50)
    run(w, 2400)
    lifted = [p.Type for p in living if p.Loaded is True or p.CarrierId.i != -1]
    handed = [int(p.BodyI) for p, _ in pads if p.BodyI is not None and int(p.BodyI) != -1]
    check("nobody alive is lifted or put on a slab", not lifted)
    check("nobody alive is handed to a pad", not any(h in [p.Id.i for p in living] for h in handed))
    check("the one real body still reaches a slab", on_a_slab(w, body))


def test_leaves_a_body_somebody_else_holds():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    w.make("MorgueSlab", 18, 20)
    guard = w.make("Guard", 26, 20)
    body = corpse(w, "Prisoner", 26, 20)
    body.Loaded = True
    body.CarrierId.i, body.CarrierId.u = guard.Id.i, guard.Id.u
    run(w, 40)
    check("a body in a guard's arms is left alone", body.CarrierId.i == guard.Id.i)


def test_will_not_lift_without_a_free_slab():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    taken = w.make("MorgueSlab", 18, 20)
    taken.Slot0.i, taken.Slot0.u = 1, 1
    body = corpse(w, "Prisoner", 26, 20)
    handed = []
    for _ in range(int(60 / STEP)):
        for env_ in w.scripts:
            env_.Update(STEP)
        w.tick()
        if this.BodyI is not None and int(this.BodyI) != -1:
            handed.append(int(this.BodyI))
    drone = w.of_kind("HaulerDrone")[0]
    check("with every slab taken no body is picked up",
          drone.Slot0.i == -1 and body.Loaded is not True)
    check("and no pad is sent after one", not handed)


def test_clears_rubbish_to_the_pad():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    bag = w.make("Garbage", 27, 24, Loaded=False)
    run(w, 60)
    check("rubbish is taken back to the pad and broken down", not w.alive(bag))
    check("the drone is empty afterwards", w.of_kind("HaulerDrone")[0].Slot0.i == -1)


def test_bodies_come_before_rubbish():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    slab = w.make("MorgueSlab", 20, 10)
    bags = [w.make("Garbage", 21 + n, 20, Loaded=False) for n in range(6)]
    run(w, 3)
    body = corpse(w, "Prisoner", 40, 20)
    order = []
    for _ in range(int(200 / STEP)):
        for env_ in w.scripts:
            env_.Update(STEP)
        w.tick()
        if slab.Slot0.i == body.Id.i and "body" not in order:
            order.append("body")
        if all(not w.alive(b) for b in bags) and "bags" not in order:
            order.append("bags")
    check("a body that turns up mid-sweep reaches the morgue before the rubbish is done",
          order[:1] == ["body"])
    check("the rubbish is cleared afterwards", order == ["body", "bags"])


def test_a_stolen_load_is_let_go_of():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    w.make("MorgueSlab", 45, 20)     # far enough that the delivery is still running
    body = corpse(w, "Prisoner", 24, 20)
    lifted = run_until(w, lambda: any(d.Slot0.i == body.Id.i for d in w.of_kind("HaulerDrone")))
    drone = w.of_kind("HaulerDrone")[0]
    check("the drone picked the body up", lifted)
    thief = w.make("Guard", 24, 20)
    body.CarrierId.i, body.CarrierId.u = thief.Id.i, thief.Id.u
    run(w, 4)
    check("a load taken by somebody else leaves the drone empty", drone.Slot0.i == -1)


def test_a_repaired_robot_is_put_down():
    """The Uplink repairs a robot guard, and one a drone lifted while it was
    down is no longer a body. It is set down where it is, not taken to a slab."""
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    slab = w.make("MorgueSlab", 60, 20)
    robot = corpse(w, "DogHandler", 24, 20)
    robot.DeathType = 0
    lifted = run_until(w, lambda: any(d.Slot0.i == robot.Id.i for d in w.of_kind("HaulerDrone")), 600)
    check("a downed robot is lifted like any body", lifted)
    robot.Damage = 0.0
    run(w, 4)
    drone = w.of_kind("HaulerDrone")[0]
    check("once repaired it is set down", drone.Slot0.i == -1 and robot.Loaded is False
          and robot.CarrierId.i == -1)
    check("and never put on a slab", slab.Slot0.i == -1)


def test_a_slab_taken_down_on_the_way():
    """A furnace takes down and rebuilds the slabs inside it, so the slab a
    drone is taking a body to can be gone when it gets there, and the next one
    it picks can go while it is on its way. The body still reaches a slab that
    is standing, and the drone is never left holding it where it stopped."""
    w = World()
    this, env = pad_at(w, 10, 10)
    with_world(w)
    first = w.make("MorgueSlab", 50, 10)
    body = corpse(w, "Prisoner", 14, 14)
    check("the body is lifted",
          run_until(w, lambda: any(d.Slot0.i == body.Id.i for d in w.of_kind("HaulerDrone")), 120))
    drone = w.of_kind("HaulerDrone")[0]
    second = w.make("MorgueSlab", 50, 30)
    first.Delete()
    check("with its slab gone it makes for the next one",
          run_until(w, lambda: abs(drone.Dest.x - 50) < 0.1 and abs(drone.Dest.y - 30) < 0.1, 120))
    w.make("MorgueSlab", 30, 30)
    second.Delete()
    check("and when that one goes too the body still reaches a standing slab",
          run_until(w, lambda: on_a_slab(w, body), 120))
    check("the drone is empty again", drone.Slot0.i == -1)


def test_a_body_in_a_wall_is_fetched():
    """A body can come to lie part way into a wall, where nobody can be sent.
    The drone comes at it from beside and lifts it from there."""
    w = World()
    this, env = pad_at(w, 10, 10)
    with_world(w)
    slab = w.make("MorgueSlab", 30, 10)
    for y in range(0, 30):
        w.walls.add((40, y))
    body = corpse(w, "Prisoner", 40.2, 20.05)
    check("a body lying in a wall reaches a slab", run_until(w, lambda: on_a_slab(w, body), 400))


def test_the_living_are_let_up_off_a_slab():
    """Anybody alive held down on a morgue slab cannot move until something
    lets go, whatever kind of staff they are. They are let up, and the dead on
    the next slab stay where they are."""
    w = World()
    this, env = pad_at(w, 10, 10)
    with_world(w)
    slabs = [w.make("MorgueSlab", 30, 20 + n) for n in range(3)]
    held = []
    for slab, kind in zip(slabs, ("Guard", "Cook")):
        person = w.make(kind, slab.Pos.x, slab.Pos.y, Damage=0.0, Loaded=True)
        person.CarrierId.i, person.CarrierId.u = slab.Id.i, slab.Id.u
        slab.Slot0.i, slab.Slot0.u = person.Id.i, person.Id.u
        held.append(person)
    dead = corpse(w, "Prisoner", slabs[2].Pos.x, slabs[2].Pos.y)
    dead.Loaded = True
    dead.CarrierId.i, dead.CarrierId.u = slabs[2].Id.i, slabs[2].Id.u
    slabs[2].Slot0.i, slabs[2].Slot0.u = dead.Id.i, dead.Id.u
    crate = w.make("DogCrate", 50, 50)
    dog = w.make("Dog", 50, 50, Damage=0.0, Loaded=True)
    dog.CarrierId.i, dog.CarrierId.u = crate.Id.i, crate.Id.u
    free = lambda: all(p.Loaded is False and p.CarrierId.i == -1 for p in held)
    check("a guard and a cook held down on slabs are let up", run_until(w, free, 900))
    check("and their slabs name nobody", slabs[0].Slot0.i == -1 and slabs[1].Slot0.i == -1)
    check("a body on its slab is left there", dead.CarrierId.i == slabs[2].Id.i and slabs[2].Slot0.i == dead.Id.i)
    check("a dog in its crate is left there", dog.Loaded is True and dog.CarrierId.i == crate.Id.i)


def test_a_drone_is_kept_whole():
    """No blow a drone takes shows, but a live cable and a deep freeze wear at
    anything standing in them. The pad mends its drone, and brings back one
    that has gone down, rather than leave it lying there."""
    w = World()
    this, env = pad_at(w, 20, 20)
    run(w, 3)
    drone = w.of_kind("HaulerDrone")[0]
    drone.Damage = 0.6
    run(w, 2)
    check("a worn drone is mended", float(drone.Damage) == 0)
    drone.Damage = 1.0
    run(w, 2)
    check("a drone that has gone down is brought back",
          float(drone.Damage) == 0 and w.of_kind("HaulerDrone") == [drone])


def test_rubbish_past_its_ground_is_left():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    w.make("Garbage", 120, 20, Loaded=False)   # well outside the pad's reach
    run(w, 60)
    drone = w.of_kind("HaulerDrone")[0]
    gap = math.hypot(drone.Pos.x - 20, drone.Pos.y - 20)
    check("a drone is never sent past its pad's ground for rubbish", gap <= 31)


def test_charge_sends_it_home():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    run(w, 3)
    this.Charge = 26.0
    corpse(w, "Prisoner", 40, 20)    # work it would otherwise fly off to
    w.make("MorgueSlab", 42, 20)
    run(w, 5)
    drone = w.of_kind("HaulerDrone")[0]
    home = math.hypot(drone.Pos.x - 20, drone.Pos.y - 20) <= 1.5
    check("a flat drone is not sent across the prison", home)
    run(w, 30)
    check("and charges back up on the pad", float(this.Charge) > 60)


def test_predator_shocks_only_the_guilty():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    run(w, 1)
    press(w, this, env, "DroneMode")
    clean = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    guilty = w.make("Prisoner", 26, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    run(w, 12)                 # long enough for the pad to take its marks
    check("a prisoner with an old record is not attacked for it",
          float(guilty.Damage) == 0 and float(clean.Damage) == 0)
    guilty.TimeOfLastMisconductPrisonerAssault = 1234.0    # misconduct, right now
    run(w, 60)
    check("a prisoner whose record has just moved is shocked", float(guilty.Damage) > 0)
    check("a prisoner whose record has not moved is left be", float(clean.Damage) == 0)
    check("the shock stops short of killing", float(guilty.Damage) <= 0.8)


def test_predator_reads_no_clock():
    """The records are written on the prison's clock and Game.Time answers with
    how long the game has been running, so the pad must never subtract one from
    the other. A record far outside the pad's own clock still has to work."""
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    run(w, 1)
    press(w, this, env, "DroneMode")
    old = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=500000.0)
    run(w, 12)
    check("a record from far outside this clock is not attacked on sight",
          float(old.Damage) == 0)
    old.TimeOfLastMisconduct = 500010.0
    run(w, 60)
    check("and is shocked once that record moves", float(old.Damage) > 0)


def test_predator_lets_a_prisoner_go():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    run(w, 1)
    press(w, this, env, "DroneMode")
    one = w.make("Prisoner", 24, 20, Damage=0.0, TimeOfLastMisconduct=900.0)
    run(w, 12)
    one.TimeOfLastMisconduct = 950.0
    run(w, 30)
    check("the shocking starts", float(one.Damage) > 0)
    run(w, 60)                 # well past the window the record opened
    settled = float(one.Damage)
    run(w, 150)
    check("and stops once the misconduct is old news", float(one.Damage) == settled)
    check("the prisoner is left alive", settled < 1.0)


def test_predator_holds_its_post():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    run(w, 1)
    press(w, this, env, "DroneMode")
    press(w, this, env, "DroneMode")
    run(w, 60)
    drone = w.of_kind("PredatorDrone")[0]
    check("on Guard Post the drone stays beside its pad",
          math.hypot(drone.Pos.x - 20, drone.Pos.y - 20) <= 6)


def test_switching_model_scraps_the_old_drone():
    w = World()
    this, env = pad_at(w, 20, 20)
    with_world(w)
    w.make("MorgueSlab", 45, 20)
    body = corpse(w, "Prisoner", 24, 20)
    check("the hauler is carrying when the model is switched",
          run_until(w, lambda: any(d.Slot0.i == body.Id.i for d in w.of_kind("HaulerDrone"))))
    press(w, this, env, "DroneMode")
    run(w, 6)
    check("the old drone is gone", not w.of_kind("HaulerDrone"))
    check("a Predator is built in its place", len(w.of_kind("PredatorDrone")) == 1)
    check("the body it was holding is put down, not lost",
          w.alive(body) and body.CarrierId.i == -1 and body.Loaded is False)


def test_world_script_clears_an_abandoned_drone():
    w = World()
    this, env = pad_at(w, 20, 20)
    world = with_world(w)
    run(w, 45)
    drone = w.of_kind("HaulerDrone")[0]
    check("a drone whose pad still stands is never swept through two sweeps", w.alive(drone))

    # something to be holding when the pad goes, and nowhere to put it down
    w.make("MorgueSlab", 45, 20)
    body = corpse(w, "Prisoner", 24, 20)
    carrying = run_until(w, lambda: drone.Slot0.i == body.Id.i)
    check("the drone is carrying before its pad goes", carrying)

    w.remove(this)                      # the pad is dismantled
    w.scripts = [world]
    run(w, 40)
    check("the abandoned drone is removed", not w.alive(drone))
    check("what it was carrying is put down rather than lost",
          w.alive(body) and body.CarrierId.i == -1 and body.Loaded is False)


def crowd(w):
    """A big prison: sixteen pads in two bays, a crowd of the living, a morgue
    and a few rubbish bags."""
    for n in range(10):
        pad_at(w, 116 + 3 * n, 95)
    for n in range(6):
        pad_at(w, 74 + 3 * (n % 2), 59 + 4 * (n // 2))
    with_world(w, (56, 8, 176, 112))
    import random
    rnd = random.Random(2)
    for kind, count in (("Prisoner", 345), ("Workman", 167), ("Guard", 122), ("Cook", 42),
                        ("Janitor", 21), ("ArmedGuard", 20), ("Gardener", 11), ("Doctor", 4)):
        for _ in range(count):
            w.make(kind, rnd.uniform(60, 170), rnd.uniform(15, 110), Damage=0.0)
    for n in range(10):
        w.make("MorgueSlab", 157, 76 + n)


def test_predators_standing_together_cost_little():
    """Predators standing side by side share one look at the prisoners round
    them, and a drone on its quarry looks only a few tiles round itself, so a
    group of them costs little more than one."""
    w = World()
    crowd(w)
    for pad in w.of_kind("DroneCharger"):
        if pad.Pos.x < 100:
            pad.Role, pad.Duty = "Predator", "Patrol"
    run(w, 30)
    import random
    rnd = random.Random(5)
    near = [p for p in w.of_kind("Prisoner") if math.hypot(p.Pos.x - 75, p.Pos.y - 63) < 30]
    w.records = 0
    for _ in range(12):
        for _ in range(20):
            for env in w.scripts:
                env.Update(STEP)
            w.tick()
        rnd.choice(near).TimeOfLastMisconduct = w.clock
    busy = w.records / 120
    shocked = sum(1 for p in near if float(p.Damage or 0) > 0)
    check("six Predators among a crowd go after the prisoners caught (%d shocked)" % shocked, shocked >= 6)
    check("and the whole prison still costs under 50 records a second (%.0f)" % busy, busy < 50)


def test_cost_stays_low():
    w = World()
    crowd(w)
    run(w, 30)                          # settle: drones built and docked
    w.records, w.searches = 0, 0
    run(w, 120)
    quiet = w.records / 120
    check("a crowded prison with nobody dead costs under 30 records a second (%.0f)" % quiet,
          quiet < 30)
    check("a standing order is not repeated every tick", w.navigations < 16 * 240)


def main():
    cases = [v for k, v in globals().items() if k.startswith("test_")]
    for case in cases:
        print("\n" + case.__name__[5:].replace("_", " "))
        case()
    print("\nfailures:", len(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
