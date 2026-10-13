# MODLOG: Portal 2 × S.T.A.L.K.E.R. Shadow of Chernobyl

## Target
- S.T.A.L.K.E.R. Shadow of Chernobyl (GOG, 1.0006 archives) at `E:\Games\S.T.A.L.K.E.R. Shadow of Chernobyl`,
  running on **OGSR Engine 3.518** (`bin_x64\xrEngine.exe`, build 2026-04-09, x64 DX11, `.pdb` shipped).
- Saves/logs: `C:\Users\User\docume~1\stalke~3\` (literal folder names, created by the GOG installer).
- The user's own AI bot hooks `bind_stalker.script` (`bot_core.on_game_update()`); our hooks sit next to it.
- Guest: Portal 2 (Steam 620) at `E:\SteamLibrary\steamapps\common\Portal 2`. Never runs; read-only asset source.

## Route
Mashup **Pattern 1 (port the content)** from `universal-modder/skills/mashup-mods`: Portal 2's mechanics are
reimplemented on the host (OGSR Lua first, engine C++ where Lua can't reach); Portal 2 assets are converted from
the user's install on their machine and never committed or shipped.

Stages:
1. **Long fall boots** (Lua only) — belt artefact; `entity_alive_before_hit` cancels the landing hit.
2. Portal gun, Lua: ray_query placement, teleport + view turn. No momentum, opaque portals.
3. OGSR C++ (build tag 3.519 to match shaders): surface normal in `rq_result`, actor velocity get/set, physics objects/NPCs through portals.
4. Portal 2 assets: viewmodel + sounds via the converter from `universal-modder/examples/outer-wilds-portal-gun`, then `.ogf` via Blender + blender-xray, `.ogg` via ffmpeg (both on E:).
5. Optional: see-through portals (OGSR has no second scene render; 3D scopes are screen-space).

## Engine facts (OGSR 3.519 source, verified by reading)
- Fall damage: `PHMovementControl::UpdateCollisionDamage` → `CActor::g_Physics` sends `GE_HIT`, type strike,
  `whoID = weaponID = actor` for static geometry. `actor.ltx`: `ph_crash_speed_min = 14`, `max = 30`.
- `callback.on_actor_land(actor, contact_speed)` fires in `Actor_Movement.cpp` when a fall ends;
  the hit event is processed after it. `callback.entity_alive_before_hit(SHit)`: `ignore_hit = true` cancels.
- `system.ltx` includes `misc\items.ltx` before artefacts, so mod sections go through `config\external.ltx`
  (included after artefacts/weapons/outfits).
- `icon_group = N` → `textures\ui\ui_icon_equipment_N.dds` (cell 50 px). Text files are cp1251.
- `-load <save>` on the command line loads a save at start (`x_ray.cpp`).
- `level.ray_query` returns range/object/element/mtl, no normal. `set_actor_position(pos, true)` zeroes velocity.

## Tools
- `tools/xrdb_unpack.py`: SoC `.db` unpacker (trivial_encryptor WW/RU, LZHUF file list, LZO1X data), ported
  from OGSR `xrCore/arc_db.cpp`. Extracted vanilla `config\` + `scripts\` to `_vanilla/` (gitignored).
- `tools/make_icons.py`: icon sheet 77. `tools/deploy.py`: backup, install, `--autotest`, `--uninstall`.

## Running tests (lab profile)
`python -I tools/deploy.py --autotest` then `python -I tools/lab.py --save all`. The lab profile
(`_lab/fsgame.ltx` via `-fsltx`, app data in `_lab/appdata`) keeps the real profile untouched; the agent's sandbox
can't write to `C:\Users\User\docume~1\stalke~3` anyway (the engine segfaults when it can't create its log).
- `-load <save>` crashes OGSR 3.518 (executes before the device exists). Use
  `-start server(<save>/single/alife/load) client(localhost)` (deferred).
- Lab `user.ltx` gets `keypress_on_start off` (no "press any key" pause) and `rs_always_active on`
  (otherwise an unfocused window stops physics while scripts keep ticking).
- `set_actor_position(pos, true)` leaves an actor that was standing still frozen in mid-air (sleeping physics
  character is not woken). `set_actor_position(pos, false)` (ForceTransform) works. Matters for portal teleports.
- Ray picks skip back faces: a ray going up from a basement passes through the terrain. "Open sky" = cast down
  from 150 m and require the first hit at the ground point.
- The repeating `c0000005` stack traces in every log come from the user's `bot_core.script:163`
  (`distance_to` on a nil vector), not from this mod.

## Video takes (the user posts them on YouTube)
`python -I tools/lab.py --save all --res 1920x1080 --record <take>` records every test: `um win record`
(gfxcapture of the game window + WASAPI loopback of the game's PID only) from "AUTOTEST armed" to 4.5 s after the
result, then `um video mux` → `_videos/<take>.mp4`. ffmpeg (BtbN, SHA-256 checked) and the capture tools are on
E: via `LOCALAPPDATA=E:\tools\um-local` (encoder h264_qsv). The autotest is paced for video and prints Russian
news lines (cp1251 renders fine). After a take, redeploy without `--autotest` (it quits the game).

## Log
- 2026-10-12: recon, unpacker, boots v1 (placeholder world model = `artefact_blackdrip.ogf`), autotest written.
- 2026-10-12: **boots verified in game** (save `all`, Cordon, outside Sidorovich's bunker, 12 m drop):
  without boots damage 0.194 at 17.4 m/s; boots on belt 0.001 at 17.3 m/s, 1 landing hit cancelled → PASS.
  Not yet seen by eye: the icon and name in the inventory UI.
- 2026-10-12: video take `_videos/boots_test_02.mp4` (1080p30, game audio, ~25 s): PASS, 19% without boots, 0% with.
- 2026-10-12: user rejected particle-based portals ("want the original portals and seeing through them") →
  engine route. OGSR built from source (`E:\github\OGSR-Engine`, branch `portal-mod`, `tools/build_ogsr.cmd`;
  fixes for MSVC 17.14: dependent static_assert, runtime quad IB; build env must clear NoDefaultCurrentDirectoryInExePath).
  Our exe goes to `<game>\bin_portal` (stock `bin_x64` untouched); `tools/lab.py --engine bin_portal`.
- E1 (`tools/engine_patches/patch_e1.py`): portals drawn in the R4 forward pass (`portal_mod_draw[2]`, shader
  `effects_portal_gun.s` / `portal_gun.vs/.ps` from Portal 2's colour ramps + noise); Lua `level.portal_set/clear`,
  `ray_query_normal`, `actor_velocity/set_actor_velocity`. Video `portals_e1_01.mp4`.
- E2 (`patch_e2.py`, docs/portal_render_plan.md): see-through. `CLevel::OnRender` maps the camera through the portal
  the player looks at, `CRender::RenderPortalView` reruns Calculate()+Render() from it with an oblique near plane on
  the exit portal (`portal_mod_pass` guards HOM, sectors, HUD, jitter, light occq, wallmarks, details, SSR, smapvis;
  resets light `frame_render`, accumulator/flare marks, imm dsgraph), copies HDR before bloom to `$user$portal0`.
  Verified on video `portals_e2_03.mp4`: identity pair = seamless transparency (NPCs at a campfire through it),
  moved exit = side view with parallax. Back-facing portals are culled.
- Gun gameplay (`pm_portals.script`): LMB/RMB shoot (ray + `ray_query_normal`, Portal 2 frame rules, fit/nudge,
  Portal 2 sounds), R closes; travel keeps momentum via `level.set_actor_velocity` (floor exits pop up >= 3.5 m/s).
  Lab scenario `gun` (`pm_gun_test.script`): finds walls with flat ground in front, shoots both, walks in with real
  input (`level.send_event_key_press` + `send_event_key_hold` every frame), drops 8 m into a floor portal.
  PASS: walk 3.6 m/s in/out; fall 16.5 m/s in -> 16.5 m/s out of the wall. Video `gun_hud_04.mp4`.
- E3 (`patch_e3.py`): `portal_mod_brief = --` -> HUD shows the gun's name instead of an ammo count (user asked for
  "something infinite" instead of gauss charges).
- Portal 2 viewmodel -> skinned OGF (`tools/p2_gun_ogf.py`): MT_SKELETON_ANIM, 3-link vertices, bind from
  pose_to_bone, IK euler via setXYZi round-trip check, embedded SMPARAMS/MOTIONS (conjugate quats, 16-bit T keys,
  StopAtEnd on one-shots). Gotcha: IKDATA game_mtl "" is looked up as a name -> write "default_object".
  `hud_fov = 54` (Portal 2 viewmodel FOV) — default HUD FOV 0.45*67.5 showed it 1.8x too big.
  `tools/preview_gun.py` renders the posed mesh in software to tell conversion bugs from HUD placement.
- User: "the gun is static, I want recoil like the original; portals should open along the surface angle".
  Our shots bypass the engine's fire (empty magazine), so no anim_shoot played. Now `pm_portals` calls
  `item:play_hud_motion("anim_shoot")` (fire1, 533 ms, logged) one update later (the engine handles the same click
  after our key callback), R plays `anim_reload` (fizzle). Portal 2 has no camera kick, only the viewmodel's.
  Placement: best-fit plane from 13 rays under the oval (Newell normal), accepts 0.25 m of bumps, orients to that
  plane, floats above the highest bump; fit failures logged with a reason (`fit_why`).
  Test gotchas: pick ground targets with line of sight from the camera (a fence ate every "ground" shot); fixed
  Cordon yard (-221.5, -140) for repeatable wall shots. Video `gun_anim_06.mp4`: PASS.
- User: "I want bullets to kill through a portal, RPGs and grenades through it, etc." + "film it in the Bar".
  E4 (`patch_e4.py`): bullets (`CBulletManager::CalcBullet`, worker thread) stop the step's ray at a portal plane
  crossed inside the oval and continue out of the other portal (direction mapped, shooter/weapon kept, tracer clipped
  to the distance since the exit); portal frames snapshot in `CommitRenderSet`. Physics bodies
  (`CLevel::PhisStepsCallback`, after each 0.01 s step): predictive crossing test, `TransformPosition` with the portal
  transform, velocities mapped, geom last positions reset (else the swept-ray contact "hits" the wall behind),
  per-object cooldown. Rocket thrust follows the body transform (XFORM lags a frame). E5 (`patch_e5.py`): one log line
  per frame with the number of bullets that went through.
  First Bar run (save `bar`, outdoor road): `wpn_rpg7_missile went through portal 0 at 46.6 m/s`, 2 of 3 bandits
  killed. AK and grenade missed by geometry: both walls ~27 m away at up to 45 deg, so the exit stream left orange at
  that angle, past bandits standing on its normal; a 25 m/s grenade aimed 1.2 m high from 27 m lands short
  (physics gravity is 19.62, not 9.81). Scenario v2 (`pm_bar_test.script`): orange on a far wall with 11 m of open
  ground, player teleported 7 m in front of blue, bandits on the exit line; aim through the portal from the "virtual
  eye" (camera mapped behind orange), grenade = low ballistic arc in the mapped space through the oval.
- Bar takes: v2 aimed through the portal, but bandits walked off the exit line (and Duty / a blind dog joined in).
  Fixes: bandits spawned at exact spots on the exit line and put under script control (stand still), switched to
  the loner community (Duty no longer shoots them first); mutants within 150 m released at setup; kills tallied per
  bandit and per weapon phase (the old alive-count difference counted corpses going offline as kills).
  E6 (`patch_e6.py`): crash fix. The sky/cloud projection switch in the portal pass called `SetCacheXform` on every
  render context while worker threads were drawing with some of them -> c0000005 in `dx10ConstantBuffer::set`
  under `R_xforms::set_V` (once, at a weapon switch). Mid-pass switches now touch only the drawing command list.
  E7 (`patch_e7.py`): Portal 2 funnelling for bodies (0.35 m around the oval) - a grenade leaves the hand bone,
  not the camera, so a throw at the portal's middle could clip its rim.
  Grenade: the quick throw (fire key, force_const 25 m/s) flew straight past the bandits and blew up far away.
  Now a charged throw: right button down, release (v - 10) / 15 s after `get_hud_item_state() == 15` (eReady;
  F1 force grows 15 m/s per second from force_min 10). `lob_plan` scans speeds 10..30 for the slowest arc (flight
  < 1.6 s) through the middle of the orange oval to half a metre in front of a bandit's feet.
  **Take `_videos/bar_portals_04.mp4`: PASS** - AK burst through the portal 2 kills, RPG (`wpn_rpg7_missile went
  through portal 0 at 18.3 m/s`) 1 kill, grenade (planned 12.5 m/s, through at 11.9 m/s) 2 kills.
  Engine commits on `portal-mod`: E4/E5/E7 `2b70282`, E6 `50b79a1`.
- NPCs and corpses (E8/E9): living NPCs/monsters are moved on the main thread like script set_npc_position plus an
  enabled physics character (a sleeping one left them hanging in the air); corpses go in the physics step, any ragdoll
  element over a floor portal makes it fall in.
- User: "walk in and out of the portal, stand in it, the view turns with the portal (like Portal 2)". Player travel
  rewritten: the surface inside a linked portal is a hole for characters, the move happens when the eye crosses the
  portal's plane, wall-to-wall it is exact (no jump), the view is mapped and its roll straightened over 0.5 s
  (`level.portal_view_roll`). Engine E10-E13, each found by logging contacts in the lab:
  * E10 `hole()`: drop character contacts with static geometry at/behind the surface inside the portal's rectangle
    (not the oval: its narrow bottom caught the feet; 0.2 m below a wall portal too), keep only ground right under the
    feet (normal within ~7 deg of the portal's up, <= 5 cm above the feet: a fence's bottom rail or a board's slanted
    lower edge is not ground). The same for the first-person camera's collision box and the activation box of
    teleports. A second portal quad 0.5 m behind the surface covers the near plane, drawn only when the camera is
    within 0.6 m (else it peeked over fences). ForceTransform resets the stair-step camera smoothing.
  * E11: no infinite friction (`pushing_neg`) for bodies inside a hole zone (it glued the player to the ground);
    the camera box ignores static geometry inside the zone; `ValidateWalkOnMesh` (the controller's own triangle query
    ahead: wall stop / step climb) treats the hole as an opening (its climb force follows a stale wall normal and
    shoved the player sideways along the wall).
  * E12: `level.portal_set_actor_position` places the player with no CollisionCorrectObjPos (its activation box
    shoved a body half inside the exit wall up to 0.5 m forward).
  * E13: the tri-list collider reports a long triangle's far vertex as the contact point (fence boards: 3.6 and 19 m
    away); hole() now uses the body's centre projected onto the contact plane when the point is > 1.5 m off. This was
    the "bumps into the fence boards" the user saw.
  Portal gun: walls accept 6 cm of bumps (floors 25 cm), denser rays catch rails and gaps, rays see physics objects
  too, a floor portal needs 2 m of free space above it (rays up and across: a fence over it is vertical planes).
  Test gotchas: a camera yaw left at -2*pi makes the body turn a full circle and walk sideways; zero leftover
  velocity before a drop. **Take `_videos/walk_portals_01.mp4`: PASS** (wall->wall exact, standing half in the
  portal, stepping through, floor->wall 13.5 m/s, wall->floor and back).
