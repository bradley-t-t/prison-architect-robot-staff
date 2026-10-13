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
is what it sends out. The one button on the pad steps through Hauler, Predator
on Patrol and Predator on Guard Post. Moving into or out of Hauler scraps the
drone the pad had and builds the other model; moving between the two Predator
duties keeps the drone.

| Model | Does |
| :--- | :--- |
| Hauler | Carries the dead from anywhere in the prison to the nearest free morgue slab. With no body waiting it lifts rubbish near its pad and takes it back to the pad, which breaks it down |
| Predator | Patrols the ground its pad covers, or holds station on it, and shocks any prisoner the game has just recorded in misconduct |

On patrol a Predator flies to whichever prisoner it can see, and to a point
somewhere in its pad's ground when it can see none. On Guard Post it stays
beside its pad and leaves only to chase somebody.

A Predator works within thirty tiles of its pad, and so does a Hauler clearing
rubbish. A Hauler goes after a body wherever it lies, however far that is from
its pad, and bodies come first: one handed to a Hauler on its way to a bag of
rubbish drops the bag. Flying drains the charge and the pad fills it back up. A
drone under half charge is not sent after a body, a drone that runs low breaks
off and comes home, and a Hauler holding something delivers it first, so
nothing is set down where nobody will look for it.

A Hauler takes a body to the free morgue slab nearest to it, which is the slab
a guard would have used. That is also what makes it work with the Crematorium
mod: the drone flies the body into the furnace's own intake and the furnace
burns it. A robot a Hauler lifted while it was down and the Robot Uplink has
since repaired is no longer a body, and is set down where it is.

A drone is staff to the game. A staff door opens for it, the route finder
takes it through one the way it takes a workman, and it is listed in the
Staff window with everybody else. It is paid nothing: the game pays staff the
Upkeep their kind names, and a drone's names none.

A drone cannot be killed. Its Toughness is a hundred thousand times a
person's, so a blow does nothing that shows, but a live cable and a deep
freeze wear at whatever stands in them however tough it is. Its pad mends it
every second, which also stands up a drone that has gone down.

### How a Hauler finds the dead

The game keeps no list of the dead. A body is a person of some kind whose
Damage has reached 1, so the only way to find one is to search for every
person of that kind, and a search hands back a full script record of each, the
living included. The game compiles every one of those records as it builds it,
so a search of every prisoner on a big map stalls the game for most of a
second. Nothing about a living person's DeathType says they are alive, either:
the game hands one to a script for the living as well as the dead, so Damage
is the only test.

So no pad searches for bodies, and nothing searches the whole map at once.
`data/world.lua` searches round the prison's lights, which stand in every room
and yard: one light near the middle of each square of the map, and more
wherever a light would otherwise be left out. One is searched every two and a
half seconds, for prisoners and for one other kind of person in turn, and a
pass of the whole map takes a minute or so. Every few seconds each Hauler free
to fly is handed the body nearest its pad and the free slab nearest that body,
and no body or slab is handed to two. A body stays remembered until it is
handed out or a later pass finds it gone, so no body is left lying however long
it has been there.

A body lying against a wall, or inside one built over it, cannot always be
flown to. A Hauler held up short of a body lifts it from where it stopped when
that is within three tiles, and otherwise makes for each spot beside the body
in turn before it hands the body back.

The same search lets up anybody alive it finds held down on a morgue slab. A
slab holds whoever lies on it the way a carrier does, so a guard or a cook put
on one stays there until something lets go. Only a slab's hold is broken: the
living are carried by other things for good reasons, a dog in its crate among
them.

### What a Predator counts as misconduct

The game writes down when a prisoner last fought, assaulted a member of staff,
killed somebody, tried to escape or caused a serious injury. A Predator watches
those records rather than reading a clock off them, and goes after a prisoner
whose record is later than it was the last time anybody looked. It wounds and
stops: a prisoner already down to a fifth of a life is left alone, so a
Predator never finishes anybody.

The looking is done by `data/world.lua`, not by the pads. A search for
prisoners hands back a full record of every one in reach, and Predators
standing side by side each searching the same prisoners every few seconds cost
more than the rest of the mod put together. So every four seconds the pads
standing within twelve tiles of each other share one search, made from the
pad nearest the middle of them, and each pad is told the nearest prisoner in
its own ground just caught in misconduct, and a prisoner to patrol towards.
Only once a drone is on its quarry does it look for itself, and then only a
few tiles round. A prisoner stays a target for forty-five seconds after the
misconduct.

Reading the clock would not have worked. `Game.Time` is `GetHighResTime`, which
is how long the game has been running, and the records are written on the
prison's own clock, which a save keeps as `TimeIndex` and which is already well
ahead of it on the first day. Subtracting one from the other gives a number
with no meaning. Watching a record move needs neither clock and fires on the
misconduct itself.

It follows that a prisoner is never shocked for something in their history. The
first time the watch sees a prisoner it takes the mark and nothing else, so a
prison just loaded, or a prisoner who walks into a Predator's ground, is gone
after for nothing already on the record.

### Where a Hauler's load is drawn

A marker is where whatever sits in slot N of an object is drawn, and its index
is that slot's number. The Hauler has one slot, so it carries one marker,
Index 0, in the middle of the cradle under its hull, repeated once per picture
in the strip so a body rides in the cradle whichever way the drone is facing.
An object with a slot and no marker has what it holds drawn at the edges of its
picture, which is a body hanging off the side.

The head, hand and foot markers the game keeps on its own people, 10 to 13,
position clothing and equipment. A drone wears none, and the Predator carries
nothing at all, so it has no slot and no marker.

### How a drone is flown

Its pad's script flies it. A script on the drone itself would put one on every
drone in the prison, and the game rebuilds its whole script API into Lua on
every one of those calls, so the thinking is done once, on the pad. A pad finds
its own drone by the id it wrote down when it built it, and then holds on to
it. A drone that has been removed reads as standing nowhere, so a pad whose
drone is still there never searches for it again.

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
| `data/world.lua` | Finds the dead and hands them to the Haulers, watches for misconduct for the Predators, lets the living up off morgue slabs, and clears a drone whose pad has gone, putting down whatever it was holding |

Install by copying `manifest.txt`, `thumbnail.png` and `data/` into a folder
under the game's `mods` directory and turning the mod on in the game.
