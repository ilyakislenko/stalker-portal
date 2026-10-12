# See-through portals in OGSR 3.519 — render plan (from reading the source)

Source: `E:\github\OGSR-Engine` (tag 3.519 + branch `portal-mod`). Paths relative to `ogsr_engine\`.

## Frame flow
- `CRenderDevice::on_idle` (xr_3da/Device.cpp:219): `FrameMove()` (L258; `dwFrame++` L469, seqFrame → `CActor::UpdateCL`
  → `CCameraManager::ApplyDevice` CameraManager.cpp:452-471 → `Device.OnCameraUpdated(true)` Actor.cpp:994),
  `OnCameraUpdated(false)` (L268, no-op if done), `Begin()`, `seqRender` (L323 → `CLevel::OnRender` xrGame/Level.cpp:430),
  `End()` (L328 → `CRender::End` r4.cpp:924; copies `*Saved` matrices Device.cpp:113-120).
- `Device::OnCameraUpdated` (Device.cpp:135-189): mInvView, mFullTransform, mInvFullTransform; `::Render->OnCameraUpdated`
  (builds ViewBase, **starts async `r_main.calculate_static()`** r4.cpp:880-897); SetCacheXform; `*_old = *Saved`; HUD matrices.
- `CLevel::OnRender`: `Render->Calculate()` (L435), `Render->Render()` (L436), bullets, reshade, PDA (L449-478), `HUD().RenderUI()`.
- `calculate_static` (r2_R_calculate.cpp:20-38): `HOM.DispatchRender()` → `main_pass_static` (r4_R_render.cpp:56; sector detect
  L63-84, PortalTraverser L120).
- `CRender::Render` (r4_R_render.cpp:266-546): jitter 292-334, sky 351, phase_scene_prepare 364, static+dynamic G-buffer 366-377
  (`main_pass_dynamic` HOM per object L220, `g_hud->Render_MAIN` L261), light occ queries 391-399, LODs/details/HUD/zb copies
  403-439, wallmarks 448, rain 454, sun cascades 457-466, emissive 468-495, smapvis 498-518, local lights 521-531, phase_combine 536.
- `phase_combine` (r4_rendertarget_phase_combine.cpp:8-307): clouds, combine_1 (33-93), SSR (98-126), forward (`render_forward`
  r4_R_render.cpp:548), hud ui, volumetric, distortion, bloom+luminance (174), tonemap (177-181), heatvision, AA (193), SSSS,
  3DSS, blur/bloom/DOF/LUT/..., motion blur combine_2 (252-278), flares, phase_pp → base RT.

## Camera state to override for a second view (and restore)
`vCameraPosition/Direction/Top/Right, mView, mInvView, mProject, mFullTransform, mInvFullTransform, fFOV, fASPECT` (device.h:55-90),
`::Render->ViewBase`, cache xform + old xform (set old = current), TAA jitter globals `ps_r_taa_jitter`/`_full` → (0,0,-1).
Do NOT touch `*Saved`, `_old`, HUD matrices; do NOT call `Device.OnCameraUpdated` (frame-guarded, side effects).
Constant binders read `Device.*` live (fog plane L97-118 uses mFullTransform; pos_decompression_params L664 uses fFOV/fASPECT;
dev_mProject L683 uses mProjectSaved).

## Existing second viewport
`rt_second_vp` = `"$user$viewport2"` (r4_rendertarget.cpp:256, R8G8B8A8, r2_types.h:76). `AfterWorldRender` (r4.cpp:230) binds it;
Level.cpp:451-477 draws the PDA **UI** into it. models_pda.s samples `s_vp2`. No path renders the world twice per frame.
Closest culling pattern for an arbitrary frustum: `R_dsgraph_structure::build_subspace` (r__dsgraph_build.cpp:655).

## Obstacles (second render in one frame)
| Area | Where | Fix |
|---|---|---|
| early main static calc | r4.cpp:890-895 | skip on portal frames; `ensure_calculate_static` (r4_R_render.cpp:369) runs it later; `r_main.wait_static()` first |
| HOM cache keyed on dwFrame | HOM.cpp:303-336; r__dsgraph_build.cpp:509/611, r4_R_render.cpp:220, r2_R_calculate.cpp:333 | `use_hom=false` for the portal pass |
| start sector | last_sector_id, main_xrc | own xrXRC; detect just in front of the EXIT portal |
| light frame_render stamp | Light_DB.cpp:127, r2_R_calculate.cpp:315 | reset `frame_render=0` afterwards |
| light vis (occlusion queries) | light_vis.cpp; r2_R_lights.cpp:124/309/327 | skip vis_prepare/update; force visible, restore |
| sun cascades | render_phase_sun.cpp | init/run/sync with portal cam; save/restore `r_sun.m_sun_cascades[]` |
| accumulator clear mark | phase_accumulator.cpp:6-14 | reset `dwAccumulatorClearMark=0` after |
| SSR / motion blur `m_saved_viewproj` statics | combine.cpp:104/257 | never run them in portal pass |
| wallmark ttl aging | WallmarksEngine.cpp:395+ | skip |
| eye adaptation | phase_bloom → phase_luminance | skip; copy HDR before bloom |
| HUD | Render_MAIN L261, hud passes 403-430, hud_ui combine:143 | exclude (+ ROS/LTRACK L172-196) |
| details | DetailManager.cpp:186/442 | skip |
| AA histories | PhaseAA | skip PhaseAA/ProcessTAA |
| leftover maps | imm dsgraph | `get_imm_context().reset()` after (r__dsgraph_build.cpp:784) |
| second thread (sound reads Device.vCameraPosition) | Device.cpp:271-311 | race: capture listener before override |

## Render target
`CRT::create(name,...)` registers by name (dx10SH_RT.cpp:223); `$user$` textures skip file loading (dx10SH_Texture.cpp:326).
Add `r2_RT_portal0 "$user$portal0"` (r2_types.h), `ref_rt rt_portal0` (r4_rendertarget.h ~L53), create in r4_rendertarget.cpp
~L256 as `DXGI_FORMAT_R16G16B16A16_FLOAT` (same as rt_Generic_0 → CopyResource). Scene HDR color = `rt_Generic_0`; copy after
forward + volumetric, before `phase_bloom` (combine ~L171). Portal mesh draws in the main forward pass (HDR) → tonemapped once.

## Oblique near plane
None exists. `build_projection` (_matrix.h:644): D3D LH, z∈[0,1], row vectors. C = exit plane in view space, camera on negative side:
```cpp
static void make_oblique(Fmatrix& P, const Fvector4& C) {
    auto sg = [](float v) { return v > 0.f ? 1.f : (v < 0.f ? -1.f : 0.f); };
    const float qx = sg(C.x) / P._11, qy = sg(C.y) / P._22, qz = 1.f, qw = (1.f - P._33) / P._43;
    const float s = 1.f / (C.x * qx + C.y * qy + C.z * qz + C.w * qw);
    P._13 = C.x * s; P._23 = C.y * s; P._33 = C.z * s; P._43 = C.w * s;
}
```
Side effects: far plane skew (build ViewBase from the non-oblique matrix + portal plane); sky dome/clouds clipped → standard
projection for them; fog plane binder; dev_mProject depth linearization (water_puddles.ps:151). G-buffer stores view-space z → fine.

## Plan
1. `Render.h`: `virtual void RenderPortalView(const Fmatrix& cam, float fov, const Fplane& exitPlane, IRender_Sector::sector_id_t s)`.
2. `r4_R_portal.cpp` `CRender::RenderPortalView`: guards; save state; set Device/ViewBase/xforms/jitter; visibility from exit sector
   (VQ_SSA only, no HOM); trimmed main_pass_dynamic (no ROS/HUD); lights forced visible; r_sun init+run; copy of Render 341-531
   minus jitter/occq/details/HUD/wallmarks/rain/smapvis; `phase_combine_portal()` = clouds + combine_1 + forward + volumetric
   → CopyResource(rt_portal0, rt_Generic_0); cleanup (sun sync/cascades, lights, package.clear, accumulator mark, imm reset,
   restore Device/ViewBase/xforms/jitter, base RT, rmNormal).
3. Hook Level.cpp before L435 (optionally every other frame).
4. `portal.s`: forward, fog(false), `dx10texture("s_portal","$user$portal0")`, UV = `hpos.xy * pos_decompression_params2.zw`.

Risks: thread race on Device.*, missed dwFrame caches (flicker/popping/double light), sky/fog under oblique projection,
TAA/DLSS ghosting (portal pixels lack velocity), ~2x GPU, actor body/HUD weapon not visible through portal, device reset.
