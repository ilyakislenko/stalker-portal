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
- User played and hit "falling through and getting stuck while walking, not even in a portal". E14
  (`patch_e14.py`): the engine never cleared its portals when a level went away (only Lua did), so after loading a
  save or changing level the old portals stayed - drawn, and holes in the collision at their old coordinates.
  ~CLevel clears them; Lua clears them too when the actor binder reinits. hole() applies only while the moving body
  is in front of the portal's opening (not to anything brushing past), and ground at/behind a wall portal counts on
  slopes up to 45 degrees unless it leans out of the wall (a board's edge). Walk test PASS twice after it.
- User: "the boots are missing". In SoC F6/F7 are quick save/load (user.ltx `bind quick_save kF6`, `quick_load kF7`):
  the dev key F6 for the boots never reached us, and F7 (our drop test) quick-loaded the game - with the E14 bug that
  left invisible portal holes behind. Dev keys moved to F8 gun, F9 boots, F10 drop test. The kit (boots + gun) is now
  put into the inventory once per game (actor pstor flag `portal_mod_kit`), not in lab scenarios. Checked in the lab
  in play mode: "kit issued", no script errors.
- User: "a main menu button that opens a menu with my mods, to switch them on and off without breaking saves".
  `mod_manager.script` + `config/ui/ui_mod_manager.xml` (styled like the options window): Portal Gun, Long Fall
  Boots and AI Bot (shown only when `bot_core.script` exists). The switches are in `$app_data_root$\mod_manager.ltx`
  (plain `id = 1/0` lines written with Lua `io`), never in a save; a switched-off mod keeps its items and sections
  and only stops acting (pm_portals closes the portals and ignores the keys, pm_boots lets fall damage through,
  the user's bot hook in bind_stalker returns early), so any save loads with any switches. deploy.py adds marked
  lines: the button before every `btn_options` in `ui_mm_main.xml` (5 layouts), its callback in
  `ui_main_menu.script`, the bot gate in `bind_stalker.script`; each line once, `--uninstall` drops them.
  OGSR's menu cursor follows the Windows cursor but only re-reads it on a DirectInput move, so a test click is
  "move x y", "rel 1 0", then "mdown"/"mup". Lab scenario `mods`: PASS (portals closed on Apply, the file written,
  switches back on); clicked in the real main menu: the window opens, Cancel returns to the menu, no log errors.
- User: "after 1-2 portal jumps the character sticks in the air, sometimes goes through textures, as if the hitbox were somewhere else". The physics character's geoms kept the tri-collider memory of the entry (last_pos for the back-trajectory test, cached triangles, neg_tri/b_neg_tri): the first step after the jump collided along the jump. E15 (`patch_e15.py`) clears it in CPHSimpleCharacter::SetPosition, as Level.cpp already did for bodies; every SetPosition caller is a teleport. Built and copied to bin_portal; not yet checked in game.
- User, more exactly: "after a few jumps I land knee-deep, then walk into air and through walls, can't fall into a floor portal by standing on it but can from a spot 5 m away". The engine's hole is the portal's rectangle (0.2 m more below a wall portal) but `travel_check` only travelled when the eye crossed inside the drawn oval: through the corners (or a wall portal's edge at eye height) the body went into the wall or floor and nobody took it to the other side, so it stayed behind the surface. `travel_check` now uses the hole's rectangle. Deployed; not yet checked in game.
- User: "no more falling in or hanging in the air, but after 1-2 jumps the portals stop taking me, even pressed against one". The first-person camera collision box (ActorCameraCollision.cpp, one shell put at the eye every frame) went behind the entry wall's plane in the hole and kept the tri-collider's pushing_neg/neg_tri after the jump: wherever the eye was still behind that (infinite) plane, the box was pushed towards it every frame and the eye left the body (knee-deep view, walls where none were seen); travel goes by the eye, so no portal was entered. E16 (`patch_e16.py`) resets the camera shell's geoms on an actor teleport (portal_mod_place, ForceTransform). In OGSR last_pos is never written after creation (always "no last position"), so E15's last_pos reset is a no-op; its cache and neg_tri reset stay. Built and copied to bin_portal; not yet checked in game.
- User: E16 fixed it. "Why don't I fly out of the other portal at the speed I went in?" The character controller (CPHSimpleCharacter::SafeAndLimitVelocity) cuts the velocity to a run every step while in control (touching the ground, a movement key held); with no key the ground friction stops it. Out of a wall portal on the floor the feet touch the floor in the first step. E17 (`patch_e17.py`): Lua `level.portal_fly_actor(v)` sets the exit velocity and, faster than 1.25 x run, keeps the character flying (b_lose_control) until it is down to that; on the ground meanwhile it skids (horizontal speed x (1 - 3 x step)). `travel()` uses it when the engine has it. Built; the mod deployed, the engine waits for the game to close to be copied; not yet checked in game.

- User: "when I look into a portal I don't see myself". In first person CActor::UpdateCL hides the actor's model (setVisible(!hud_view)). E18 (`patch_e18.py`) makes it visible for the portal pass only (CLevel portal_mod_render_view, around RenderPortalView) and hides it again for the main view: the body and the gun in its hands are seen through a portal. Lab scenario `mirror` (`pm_mirror_test.script`): blue on the yard's fence, orange placed free-standing 8 m out facing it, the player between them looks into blue. User checked it in game: works.
- User: "from one portal the other is not seen". The see-through pass skipped the portal draw (`portal_mod_pass ||` in r4_R_render.cpp). E19 (`patch_e19.py`) draws them in the pass too: the exit portal is behind the pass's camera and drops out by the facing test; the entry one shows last frame's view (rt_portal0 still holds it while the pass renders into rt_Generic_0; Level.cpp sets portal_mod_view_prev before resetting params.w) - Portal 2's tunnel, one frame deeper each frame, no extra pass; closed (the swirl) before any view exists. Seen in the `mirror` take: a blue portal inside the blue portal.
- User: "and sounds" + the gun's world model was still the Gauss. `tools/p2_world.py` (universal-modder venv python) reads `models/weapons/w_portalgun` from Portal 2's VPKs with universal-modder's Source readers, writes `_p2/w_portalgun.owpg` and `meshes/portal_mod/wpn_portalgun.ogf`: MT_SKELETON_RIGID, one bone `wpn_body` with a box shape = the mesh bounds (the dropped gun's physics shell), mass 2.5, all vertices in the bind pose. The converter's world model lies on its side (up along x, claws along y): ORIENT read off shaded orthographic views of the mesh (no mirror, det +1); muzzle +z. `visual`, `position`, `fire_point` in [wpn_portalgun]. Loads, drops and spawns on the ground without errors; its look in hands/on the ground (and whether it is upside down) is to be judged by eye.
- Sounds wired (all Portal 2): the open portal's hum `wpn_portal_ambient_lp_01` (3D loop at each portal, stopped on remove), `portal_close1/2` at each portal on R, `portal_exit_0N` after the entry sound, the gun's `portalgun_powerup1` (picked up), `wpn_portalgun_activation_01` (drawn), `portalgun_powerdown` (put away), the long fall boots' `longfall_land_0N` when a fall is cancelled. The hum and the landings are read by `p2_assets.py` itself (EXTRA_SOUNDS) - the converter's list lacks them. Lab `boots` PASS with the landing sound, no script errors.
- Lab `gun` measured the exit speed in the travel frame; since E17 the exit velocity is set in the next physics step (it read 0) - now read 0.2 s later. Still flaky: of three runs one PASS (19.8 m/s out), one 0 m/s out of the wall portal, one never came through the blue portal. Open.
- User: "sometimes the energy is kept, sometimes 0". Lab `gun` frame by frame after a floor->wall travel (4 runs, the exit portal standing on the ground): the exit velocity (E17) is set every time, 19.6 m/s, no instant zero; but for ~0.1 s the body barely moves (0.1-0.15 m a frame at 19.6 m/s - held at the exit, likely by the hole's edges with the wall 0.48 m behind the feet), then it flies, touches the ground within a few frames and the speed falls in steps (19.7 -> 12 -> 9.5 -> 8 -> 7.2: a contact, not E17's 3/s skid); under a run E17's fly mode ends, the controller takes over and with no key held it stops dead. So from a portal at ground level the momentum lasts about half a second. The test judged the speed 0.6 s late (0 by then): now the fastest real movement after the travel. Open: the hold at the exit and the hard stop on the ground.
- The physics steps logged (a temporary engine Msg per CPHSimpleCharacter::PhDataUpdate after a portal fly): out of the wall portal the body did fly at 19.4 m/s (the Lua-side 'held' frames were sampling jitter); on touching the ground it lost 40 % in one step, then ~8 % a step. InitContact gives the character's contacts the material's full friction whenever no movement key is held (`is_control` contacts are frictionless) - the user's "sometimes 0" = no key held. E20 (`patch_e20.py`): while E17's m_portal_fly the contacts are frictionless and the ground slows the player by Source's rule (sv_friction 4, sv_stopspeed 1.9 m/s: drop = max(speed, 1.9) * 4 * dt a step). Lab `gun`, 2 of 2 PASS: 12-15 m out of a ground-level wall portal in about a second, then a stop (was 3-4 m and a dead stop).
- User after E20: "fun - after each exit he speeds up, breaking the conservation of energy. Let it stay, it's funny." Kept on purpose: do not "fix" the speed gained per exit (likely the floor exits' minimum pop-up speed and the contact solver pushing the frictionless body out of the ground).
- User: "the game hitches every third or half a second while running or walking". Lab scenario `stutter` (`pm_stutter_test.script`: 10 s of the forward key, every frame's length): with My Mods' AI bot on, 13 ms a frame and bursts of ~6 frames of 20-30 ms every ~0.3 s; with it off, 8 ms and no frame over 20 ms. The bot's in-game half scanned and wrote its state every 100 ms with no brain attached (and an old cmd.txt in E:\stalker-botuntime made it think one was). Fixed in the bot (E:\stalker-bot cff4f18 + next: idle unless a brain's heartbeat changes this session), installed into the game: bot on, no brain -> 8.0 ms, max 21 ms. My Mods' AI bot switch off skips its code altogether.
