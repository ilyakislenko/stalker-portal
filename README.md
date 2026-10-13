# S.T.A.L.K.E.R. × Portal 2

A mod for **S.T.A.L.K.E.R.: Shadow of Chernobyl** on [OGSR Engine](https://github.com/OGSR/OGSR-Engine) that brings
Portal 2's mechanics into the Zone.

- **Long Fall Boots** (a belt artefact): no fall damage.
- **Portal Gun** with Portal 2's viewmodel and sounds: blue and orange portals, a live view through them (a second
  render pass), portals that lie flat on the surface they hit.
- **Walking through portals like in Portal 2**: the surface inside a portal is a hole for the body, so you walk into a
  wall portal, can stand half inside it and fall into a floor portal; you are moved the moment your eye crosses the
  portal, so between two wall portals there is no jump at all. The view turns with the portals and its roll
  straightens out, as in Portal 2.
- **Everything goes through portals**: the player (momentum kept), bullets, RPG rockets, grenades (with Portal 2 style
  funnelling), physics objects, NPCs, mutants and corpses. Whatever stands on a floor portal falls in.

Work in progress. The full log of decisions, engine facts and pitfalls is in [MODLOG.md](MODLOG.md).

## Requirements

- S.T.A.L.K.E.R.: Shadow of Chernobyl (GOG) running on OGSR Engine 3.518.
- OGSR Engine sources (tag 3.519), Visual Studio 2022 with C++, Python 3.11.
- **Portal 2 installed**: its textures, sounds and portal gun model are converted by the scripts from your own copy
  of the game. This repository contains no Portal 2 assets and no files from the S.T.A.L.K.E.R. archives.

The scripts still have the author's paths hardcoded (`E:\Games\...`, `E:\github\OGSR-Engine`, `E:\SteamLibrary\...`):
change them at the top of `tools/*.py` and in `tools/build_ogsr.cmd`.

## Building

1. Engine: the ready-to-build source is the `portal-mod` branch of
   [ilyakislenko/OGSR-Engine](https://github.com/ilyakislenko/OGSR-Engine/tree/portal-mod) (OGSR Engine plus the
   portal patches and two build fixes for MSVC 17.14). Build it with `tools\build_ogsr.cmd` (or Visual Studio, x64
   Release) and copy `bin_x64\xrEngine.exe` into the game folder as `bin_portal\xrEngine.exe` (the stock `bin_x64`
   stays untouched). The same changes as scripts for any OGSR checkout: `tools/engine_patches/patch_e1.py` …
   `patch_e14.py`, applied in order (`python -I tools/engine_patches/patch_eN.py`).
2. Portal 2 assets: `tools/p2_assets.py` (textures, sounds), `tools/p2_gun_ogf.py` (the gun model as OGF),
   `tools/make_icons.py` (inventory icons). Output goes to `_gen/` (not in git).
3. Install into the game: `python -I tools/deploy.py` (backs up, installs `mod/gamedata` + `_gen/gamedata`, adds hooks
   to `bind_stalker.script`). Remove with `--uninstall`.

Run `bin_portal\xrEngine.exe`.

## Controls

| Key | Action |
|---|---|
| F8 | give the portal gun (dev mode) |
| F6 | give the long fall boots |
| LMB / RMB | blue / orange portal |
| R | close the portals |

## Tests

`tools/lab.py` runs the game on a separate lab profile with an autotest scenario and records a video
(`python -I tools/deploy.py --autotest bar`, then `python -I tools/lab.py --engine bin_portal --save bar --record take`).
Scenarios: `boots`, `portals`, `gun`, `bar` (shooting through portals), `npc` (NPCs and corpses through a floor
portal), `walk` (walking into portals, standing in one, floor and wall portals).
