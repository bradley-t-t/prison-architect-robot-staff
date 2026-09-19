# Robot Guards

A Prison Architect mod. Your Guards, Armed Guards and Dog Handlers are robots.

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
lights down, which is the game's blink. Guards keep the game's guard blue,
Armed Guards are gunmetal with a belt of shells, and Dog Handlers are navy with
a K-9 plate.

The game draws a guard's stab vest over whatever the guard looks like, cut to
a person's shoulders, which on a robot is a dark bib across the chest. The mod
ships the game's people sheet with the vest's pictures emptied, so a vest
still protects and is still named on the guard, and nothing is drawn for it.

## What a robot is

- It never tires. The three kinds carry the game's own `DoesNotTire`.
- It is never corrupt. The mod ships the game's `crookedguards_settings.txt`
  with every line that decides whether a guard turns set out of reach.
- It takes twice the punishment. Toughness is doubled, and damage works as it
  always did, so a robot can still be destroyed.

Everything else about a guard, its speed, price, wages, equipment and
research, is read from the game's own definition when the mod is built.

The Robot Uplink is the backstop. Build one anywhere and it looks at one kind
of guard every six seconds, tops up the charge of a robot that is flagging and
wipes clean one that was already corrupt when the mod was switched on.

## What it cannot do

The game decides which staff have needs from a list built into it, and Guards
are on that list, so a mod cannot take the toilet and the canteen away from
guards alone. The game's own Staff Needs option turns needs off for all staff.

The mod redefines the Guard, the Armed Guard and the Dog Handler, so any other
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
