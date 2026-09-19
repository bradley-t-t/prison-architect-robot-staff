# Robot Guards

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
a person's shoulders, which on a robot is a dark bib across the chest. The mod
ships the game's people sheet with the vest's pictures emptied, so a vest
still protects and is still named on the guard, and nothing is drawn for it.

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
of guard every six seconds, tops up the charge of a robot that is flagging,
repairs one that is damaged and wipes clean one that was already corrupt when
the mod was switched on.

## What it cannot do

The game decides which staff have needs from a list built into it, and Guards
are on that list, so a mod cannot take the toilet and the canteen away from
guards alone. The game's own Staff Needs option turns needs off for all staff.

The mod redefines every kind of staff, so any other
mod that does the same, Additional Guard Sprites for one, has to be off, and
so does any mod that ships its own `people.png`.

## Layout

| Path | Holds |
| :--- | :--- |
| `tools/robots.py` | Draws the robots |
| `tools/gen_assets.py` | Builds the sprite sheet, `materials.txt`, the settings file, the language file and the thumbnail from the game's unpacked data folder |
| `tools/simulate.py` | Runs the uplink script against a stand-in for the game and checks it |
| `data/scripts/RobotUplink.lua` | The uplink, written by hand |

Install by copying `manifest.txt`, `thumbnail.png` and `data/` into a folder
under the game's `mods` directory and turning the mod on in the game.
