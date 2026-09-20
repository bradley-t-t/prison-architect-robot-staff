# Robot Staff

A Prison Architect mod. Your staff are robots, and the ones that guard are
built for it.

## The robots

Four models, and the game deals them out the way it deals out its own four
guard builds:

| Model | Looks like |
| :--- | :--- |
| Patrol | A rounded steel head under a peaked cap plate with a gold badge, a slim cyan visor, a core and a shield on the chest |
| Heavy | A squat head sunk between big pauldrons carrying a red and a blue siren, slanted amber eyes, a vented chest and a hazard band |
| Scout | A tall drum of a head on a thin neck with one green lens, a whip antenna and a striped sash |
| Enforcer | A wedge head with a red T visor, twin stub antennae, plated shoulders and a gold chevron |

Each is drawn from the front, the back and the side, and once more with its
lights down, which is the game's blink.

Every kind of staff is those four models in its own uniform, the colours the
game dresses that kind in, with its own mark over the top: Guards in guard
blue, Armed Guards in gunmetal with a belt of shells, Dog Handlers in navy
with a K-9 plate, Snipers in olive, Workmen and the Foreman in hi-vis with
reflective stripes, Cooks in white with an apron, Janitors, Gardeners and
Farmers in their overalls, Doctors, Orderlies and the Psychiatrist with a red
cross, and the Warden, Chief, Psychologist, Accountant and Lawyer in their
suits with a gold band.

The game draws a guard's stab vest over whatever the guard looks like, cut to
a person's shoulders, which on a robot is a dark bib across the chest. The game
takes the vest's pictures from its uniform packs in `data/sprite_replacement`,
so the mod ships an empty picture in place of each one. A vest still protects
and is still named on the guard, and nothing is drawn for it.

## What a robot guard is

Guards, Armed Guards and Dog Handlers are more than a new look.

- It never tires. The three kinds carry the game's own `DoesNotTire`.
- It is never corrupt. The mod ships the game's `crookedguards_settings.txt`
  with every line that decides whether a guard turns set out of reach.
- It cannot be killed. The game divides every blow by the Toughness of
  whoever it lands on, and a robot guard's is a hundred thousand times a
  person's, so a blow does nothing that shows. The Robot Uplink repairs
  whatever damage one still carries.

Everything else about a member of staff, its speed, price, wages, equipment
and research, is read from the game's own definition when the mod is built,
and for every kind but those three the look is the only thing that changes.

The Robot Uplink is the backstop. Build one anywhere and it looks at one kind
of robot every three seconds, tops up the charge of a robot that is flagging,
repairs one that is damaged and wipes clean one that was already corrupt when
the mod was switched on.

## What every robot is

No robot tires and no robot has needs. Every kind carries the game's own
`DoesNotTire`, and the mod ships the game's `needs-staff.txt` with nothing left
to drive a need. The game raises a need over time only while its definition
carries `AutoCharge`, and it reads that from the definition every tick rather
than from the save, so with the property gone the toilet, the canteen and the
rest stop for the staff a prison already has. `Chance` is how likely a new
member of staff is to be given a need at all, and at nought nobody hired from
then on has any. A need that was already high when the mod was switched on is
met once, in the ordinary way, and does not come back.

The Robot Uplink recharges every kind of robot, not only the guards.

## Drones

A Drone Bay is a room with at least one Drone Charger standing in it, and each
pad builds one drone and keeps it flying. The pad is what you build; the drone
is what it sends out. The button on the pad picks which of the two models it
builds, and switching a pad scraps the drone it had and builds the other.

| Model | Does |
| :--- | :--- |
| Hauler | Carries the dead to the morgue. With no body waiting it lifts rubbish and takes it back to the pad, which breaks it down |
| Predator | Patrols the ground its pad covers, or holds station on it, and shocks any prisoner the game has just recorded in misconduct |

A Predator has a second button for its duty. On patrol it flies to whichever
prisoner it can see, and to a point somewhere in its pad's ground when it can
see none. On Guard Post it stays beside its pad and leaves only to chase
somebody.

A drone works within thirty tiles of its pad and is never sent further, so you
cover a prison by putting a pad in each part of it rather than by building one
and waiting. Flying drains the charge and the pad fills it back up. A drone
that runs low breaks off and comes home, and a Hauler holding something
delivers it first, so nothing is set down where nobody will look for it.

A Hauler takes a body to the nearest morgue slab that is free, which is the
slab a guard would have used. That is also what makes it work with the
Crematorium mod: the drone flies the body into the furnace's own intake and the
furnace burns it.

### What a Predator counts as misconduct

The game writes down when a prisoner last fought, assaulted a member of staff,
killed somebody, tried to escape or caused a serious injury. A Predator watches
those records rather than reading a clock off them, and goes after a prisoner
whose record is later than it was the last time the pad looked. It wounds and
stops: a prisoner already down to a fifth of a life is left alone, so a
Predator never finishes anybody.

Reading the clock would not have worked. `Game.Time` is `GetHighResTime`, which
is how long the game has been running, and the records are written on the
prison's own clock, which a save keeps as `TimeIndex` and which is already well
ahead of it on the first day. Subtracting one from the other gives a number
with no meaning. Watching a record move needs neither clock and fires on the
misconduct itself.

It follows that a prisoner is never shocked for something in their history. The
first time a pad sees a prisoner it takes the mark and nothing else, so a pad
just built, or a prison just loaded, goes after nobody.

### How a drone is flown

Its pad's script flies it. A script on the drone itself would put one on every
drone in the prison, and the game rebuilds its whole script API into Lua on
every one of those calls, so the thinking is done once, on the pad. A pad finds
its own drone by the id it wrote down when it built it.

The one thing written on a drone is its name, and that is a lease. A pad marks
its drone every second; `data/world.lua` takes the mark off on its sweep and
removes anything still unmarked when the next sweep comes round. A pad that is
still standing has marked its drone again long before then. A drone whose pad
has been dismantled is never marked again, and goes, and whatever it was
carrying is put down first.

## Conflicts

The mod redefines every kind of staff, so any other
mod that does the same, Additional Guard Sprites for one, has to be off, and
so does any mod that replaces the stab vest's pictures in `sprite_replacement`.

## Layout

| Path | Holds |
| :--- | :--- |
| `tools/robots.py` | Draws the robots |
| `tools/drones.py` | Draws the drones and their pad |
| `tools/gen_assets.py` | Builds the sprite sheet, `materials.txt`, the settings file, the language file and the thumbnail from the game's unpacked data folder |
| `tools/simulate.py` | Runs the uplink script against a stand-in for the game and checks it |
| `tools/simulate_drones.py` | Runs the pad and the world script against a stand-in for the game and checks what the drones do with it |
| `data/scripts/RobotUplink.lua` | The uplink, written by hand |
| `data/scripts/DroneCharger.lua` | The pad, which flies the drone it owns |
| `data/world.lua` | Clears a drone whose pad has gone, and puts down whatever it was holding |

Install by copying `manifest.txt`, `thumbnail.png` and `data/` into a folder
under the game's `mods` directory and turning the mod on in the game.
