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

## Conflicts

The mod redefines every kind of staff, so any other
mod that does the same, Additional Guard Sprites for one, has to be off, and
so does any mod that replaces the stab vest's pictures in `sprite_replacement`.

## Layout

| Path | Holds |
| :--- | :--- |
| `tools/robots.py` | Draws the robots |
| `tools/gen_assets.py` | Builds the sprite sheet, `materials.txt`, the settings file, the language file and the thumbnail from the game's unpacked data folder |
| `tools/simulate.py` | Runs the uplink script against a stand-in for the game and checks it |
| `data/scripts/RobotUplink.lua` | The uplink, written by hand |

Install by copying `manifest.txt`, `thumbnail.png` and `data/` into a folder
under the game's `mods` directory and turning the mod on in the game.
