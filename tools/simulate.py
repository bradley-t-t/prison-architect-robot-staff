"""Runs data/scripts/RobotUplink.lua against a stand-in for the game and checks
that it tops up a flagging robot, wipes a corrupted one, writes to nobody who
needs nothing, and searches the map once a round.

Usage: python simulate.py      (needs lupa)
"""

import collections
import os
import sys

from lupa import LuaRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lua = LuaRuntime(unpack_returned_tuples=True)
g = lua.globals()
searches, writes = [0], [0]
make = lua.eval("function(e, c) return { Energy = e, Corrupted = c, Damage = 0 } end")
robots = collections.defaultdict(list)
robots.update({"Guard": [make(95, False), make(20, False), make(90, True)],
          "ArmedGuard": [make("55.5", True)], "DogHandler": [], "Cook": [make(10, True)]})


def find(kind, _reach):
    searches[0] += 1
    t = lua.eval("{}")
    for r in robots[kind]:
        t[r] = "1"
    return t


def put(robot, name, value):
    writes[0] += 1
    robot[name] = value


g.this = lua.eval("{}")
g.Object = lua.table_from({"GetNearbyObjects": find, "SetProperty": put})
lua.execute(open(os.path.join(ROOT, "data", "scripts", "RobotUplink.lua")).read())
robots["DogHandler"].append(make(100, False))
robots["DogHandler"][0].Damage = 0.4
for _ in range(1200):
    g.Update("0.1")

failures = []


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


everyone = [r for kind in robots.values() for r in kind]
check("every robot is charged", all(float(r.Energy) >= 70 for r in everyone))
check("no robot guard is corrupt", not any(r.Corrupted for kind in ("Guard", "ArmedGuard", "DogHandler") for r in robots[kind]))
check("a cook is recharged and otherwise untouched", float(robots["Cook"][0].Energy) == 100 and robots["Cook"][0].Corrupted)
check("a damaged robot is repaired", robots["DogHandler"][0].Damage == 0)
check("only the robots that needed it were written to", writes[0] == 6)
check("one map search a round", searches[0] <= 41)
check("the tooltip counts the robots", list(g.this.Tooltip.values())[1] == 6)
print("failures:", len(failures))
sys.exit(1 if failures else 0)
