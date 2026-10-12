"""portal-mod engine patch E2: see-through portals.

Before the main frame, CLevel::OnRender picks the linked portal the camera looks at, maps the camera through it
(a half turn about the portal's up axis) and calls Render->RenderPortalView(). That runs the normal
Calculate()+Render() pipeline from the virtual camera with an oblique near plane on the exit portal, with
portal_mod_pass = true so per-frame state of the main camera is left alone (HOM, sectors, HUD, TAA jitter,
light occlusion queries, wallmarks, details, SSR, smapvis), stops in phase_combine before bloom and copies the HDR
scene colour to $user$portal0. The portal shader samples it with screen-space UVs. See docs/portal_render_plan.md.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E2"


def patch(rel, edits):
    p = ENG / rel
    raw = p.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    if MARK in s:
        print("skip (already patched)", rel)
        return
    nl = "\r\n" if "\r\n" in s else "\n"
    for anchor, how, text in edits:
        anchor = anchor.replace("\n", nl)
        text = text.replace("\n", nl)
        n = s.count(anchor)
        if n != 1:
            raise SystemExit(f"{rel}: anchor found {n} times: {anchor!r}")
        i = s.index(anchor)
        if how == "replace":
            s = s[:i] + text + s[i + len(anchor):]
        else:
            at = i + len(anchor) if how == "after" else i
            s = s[:at] + text + s[at:]
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))
    print("patched", rel)


patch("xr_3da/Render.h", [
    ("ENGINE_API extern PORTAL_MOD_DRAW portal_mod_draw[2];\n", "after",
     "ENGINE_API extern bool portal_mod_pass; // portal-mod E2: true while the renderer draws the view through a portal\n"
     "ENGINE_API extern Fmatrix portal_mod_full_std; // portal-mod E2: that view's full transform without the oblique near plane\n"),
    ("    virtual void AfterWorldRender() = 0;", "before",
     "    virtual void RenderPortalView(const Fvector& pos, const Fvector& dir, const Fvector& top, const Fplane& clip) {} // portal-mod E2\n"),
])

patch("xr_3da/Render.cpp", [
    ("ENGINE_API PORTAL_MOD_DRAW portal_mod_draw[2]{}; // portal-mod\n", "after",
     "ENGINE_API bool portal_mod_pass{}; // portal-mod E2\nENGINE_API Fmatrix portal_mod_full_std{};\n"),
])

patch("Layers/xrRenderPC_R4/r4.h", [
    ("    void AfterWorldRender() override;", "before",
     "    void RenderPortalView(const Fvector& pos, const Fvector& dir, const Fvector& top, const Fplane& clip) override; // portal-mod E2\n"
     "    void portal_mod_projection(bool standard);\n"
     "    Fmatrix portal_mod_P_std{}, portal_mod_P_obl{};\n"),
])

patch("Layers/xrRenderPC_R4/r2_types.h", [
    ('#define r2_RT_generic0 "$user$generic0"', "after", '\n#define r2_RT_portal0 "$user$portal0" // portal-mod E2'),
])

patch("Layers/xrRenderPC_R4/r4_rendertarget.h", [
    ("    ref_rt rt_second_vp;", "before", "    ref_rt rt_portal0; // portal-mod E2: HDR view through a portal\n"),
    ("    ref_shader s_portal_gun; // portal-mod\n", "after",
     "    void portal_mod_reset_marks() { dwAccumulatorClearMark = 0; dwFlareClearMark = 0; } // portal-mod E2\n"),
])

patch("Layers/xrRenderPC_R4/r4_rendertarget.cpp", [
    ("        rt_second_vp.create(r2_RT_secondVP, w, h, DXGI_FORMAT_R8G8B8A8_UNORM);", "before",
     "        rt_portal0.create(r2_RT_portal0, w, h, DXGI_FORMAT_R16G16B16A16_FLOAT); // portal-mod E2\n"),
])

patch("Layers/xrRender/HOM.h", [
    ("    bool Allowed() const { return !ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_HOM) && m_pModel; }", "replace",
     "    // portal-mod E2: no occlusion culling for the view through a portal (its results are cached per frame for the main camera)\n"
     "    bool Allowed() const { return !portal_mod_pass && !ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_HOM) && m_pModel; }"),
])

patch("Layers/xrRender/Blender_Recorder_StandartBinding.cpp", [
    ("        const Fmatrix& M = Device.mFullTransform;\n        plane.x = -(M._14 + M._13);", "replace",
     "        const Fmatrix& M = portal_mod_pass ? portal_mod_full_std : Device.mFullTransform; // portal-mod E2: fog from the camera, not the oblique near plane\n"
     "        plane.x = -(M._14 + M._13);"),
])

patch("Layers/xrRenderPC_R4/r4_rendertarget_phase_combine.cpp", [
    ("        g_pGamePersistent->Environment().RenderClouds(cmd_list);", "replace",
     "        if (portal_mod_pass) // portal-mod E2: the cloud dome would be clipped by the oblique projection\n"
     "            RImplementation.portal_mod_projection(true);\n"
     "        g_pGamePersistent->Environment().RenderClouds(cmd_list);\n"
     "        if (portal_mod_pass)\n"
     "            RImplementation.portal_mod_projection(false);"),
    ("    if (ps_r2_ls_flags_ext.test(R2FLAGEXT_SSLR) && !fis_zero(g_pGamePersistent->Environment().wetness_factor))\n    {\n        PIX_EVENT(PHASE_SSR_BLUR);",
     "replace",
     "    if (!portal_mod_pass && ps_r2_ls_flags_ext.test(R2FLAGEXT_SSLR) && !fis_zero(g_pGamePersistent->Environment().wetness_factor)) // portal-mod E2\n    {\n        PIX_EVENT(PHASE_SSR_BLUR);"),
    ("        RImplementation.render_forward();\n    }\n", "after",
     "\n    // portal-mod E2: the view through a portal ends here, HDR, before bloom/tonemap/AA: the portal shader samples it\n"
     "    if (portal_mod_pass)\n    {\n"
     "        HW.get_context(cmd_list.context_id)->CopyResource(rt_portal0->pSurface, rt_Generic_0->pSurface);\n"
     "        return;\n    }\n"),
])

patch("Layers/xrRenderPC_R4/r4_R_render.cpp", [
    ("    if (!ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_SECTORS))\n    {\n        // Detect camera-sector", "replace",
     "    if (!portal_mod_pass && !ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_SECTORS)) // portal-mod E2: the portal view takes all sectors\n    {\n        // Detect camera-sector"),
    ("    if (dsgraph.phase == PHASE_NORMAL)\n    {\n        // update light-vis for current entity / actor", "replace",
     "    if (dsgraph.phase == PHASE_NORMAL && !portal_mod_pass)\n    {\n        // update light-vis for current entity / actor"),
    ("                if (dsgraph.PortalTraverser.frame() == Device.dwFrame && distance > 15.f)", "replace",
     "                if (!portal_mod_pass && dsgraph.PortalTraverser.frame() == Device.dwFrame && distance > 15.f)"),
    ("        if (dsgraph.phase == PHASE_NORMAL)\n        {\n            g_hud->Render_MAIN(dsgraph.context_id);", "replace",
     "        if (dsgraph.phase == PHASE_NORMAL && !portal_mod_pass)\n        {\n            g_hud->Render_MAIN(dsgraph.context_id);"),
    ("    if (ps_pnv_mode < 2 && (ps_r_pp_aa_mode == DLSS", "replace",
     "    if (!portal_mod_pass && ps_pnv_mode < 2 && (ps_r_pp_aa_mode == DLSS"),
    ("        g_pGamePersistent->Environment().RenderSky(cmd_list);", "replace",
     "        if (portal_mod_pass) // portal-mod E2: sky dome with the standard projection\n"
     "            portal_mod_projection(true);\n"
     "        g_pGamePersistent->Environment().RenderSky(cmd_list);\n"
     "        if (portal_mod_pass)\n"
     "            portal_mod_projection(false);"),
    ("        LP_normal.vis_prepare(cmd_list);", "replace",
     "        if (!portal_mod_pass) // portal-mod E2: light occlusion queries belong to the main camera\n"
     "            LP_normal.vis_prepare(cmd_list);"),
    ("        if (Details)\n            Details->Render(cmd_list);", "replace",
     "        if (Details && !portal_mod_pass)\n            Details->Render(cmd_list);"),
    ("            dsgraph.r_dsgraph_render_hud();", "replace",
     "            if (!portal_mod_pass)\n                dsgraph.r_dsgraph_render_hud();"),
    ("            dsgraph.r_dsgraph_render_hud_scope_depth();", "replace",
     "            if (!portal_mod_pass)\n                dsgraph.r_dsgraph_render_hud_scope_depth();"),
    ("    if (Wallmarks)\n    {\n        PIX_EVENT(DEFER_WALLMARKS);", "replace",
     "    if (Wallmarks && !portal_mod_pass)\n    {\n        PIX_EVENT(DEFER_WALLMARKS);"),
    ("    if (!Lights_LastFrame.empty() && !ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_SMAPVIS))", "replace",
     "    if (!portal_mod_pass && !Lights_LastFrame.empty() && !ps_r2_ls_flags_ext.test(R2FLAGEXT_DISABLE_SMAPVIS))"),
    ("    LP_normal.vis_update();\n", "replace",
     "    if (!portal_mod_pass)\n        LP_normal.vis_update();\n"),
    ("        if (ps_r2_ls_flags_ext.test(R2FLAGEXT_SSLR) && !fis_zero(Env.wetness_factor))", "replace",
     "        if (!portal_mod_pass && ps_r2_ls_flags_ext.test(R2FLAGEXT_SSLR) && !fis_zero(Env.wetness_factor))"),
    ("            if (!portal.on || !ViewBase.testSphere_dirty(", "replace",
     "            if (portal_mod_pass || !portal.on || !ViewBase.testSphere_dirty("),
])

# the new pass itself, appended to r4_R_render.cpp
p = ENG / "Layers/xrRenderPC_R4/r4_R_render.cpp"
s = p.read_bytes().decode("utf-8-sig")
if "void CRender::RenderPortalView" not in s:
    nl = "\r\n" if "\r\n" in s else "\n"
    code = r'''
// portal-mod E2 -------------------------------------------------------------------------------------------------------
// Oblique near plane (Lengyel; D3D z in [0,1], row vectors). C = clip plane in view space, camera on its negative side.
static void portal_mod_make_oblique(Fmatrix& P, const Fvector4& C)
{
    auto sg = [](float v) { return v > 0.f ? 1.f : (v < 0.f ? -1.f : 0.f); };
    const float qx = sg(C.x) / P._11, qy = sg(C.y) / P._22, qz = 1.f, qw = (1.f - P._33) / P._43;
    const float s = 1.f / (C.x * qx + C.y * qy + C.z * qz + C.w * qw);
    P._13 = C.x * s;
    P._23 = C.y * s;
    P._33 = C.z * s;
    P._43 = C.w * s;
}

void CRender::portal_mod_projection(bool standard)
{
    Device.mProject.set(standard ? portal_mod_P_std : portal_mod_P_obl);
    Device.mFullTransform.mul(Device.mProject, Device.mView);
    Device.mInvFullTransform.invert_44(Device.mFullTransform);
    SetCacheXform(Device.mView, Device.mProject);
}

// The world seen from a virtual camera (the camera mapped through a portal) into rt_portal0, before the main frame.
void CRender::RenderPortalView(const Fvector& pos, const Fvector& dir, const Fvector& top, const Fplane& clip)
{
    if (!g_pGameLevel || ShouldSkipRender() || m_bFirstFrameAfterReset)
        return;

    ZoneScoped;

    // OnCameraUpdated already started the main camera's static visibility: finish it, drop it, redo it afterwards.
    r_main.sync();
    get_imm_context().reset();

    const Fvector s_pos = Device.vCameraPosition, s_dir = Device.vCameraDirection, s_top = Device.vCameraTop, s_right = Device.vCameraRight;
    const Fmatrix s_view = Device.mView, s_inv_view = Device.mInvView, s_proj = Device.mProject, s_full = Device.mFullTransform,
                  s_inv_full = Device.mInvFullTransform;
    const CFrustum s_base = ViewBase;

    Device.vCameraPosition.set(pos);
    Device.vCameraDirection.set(dir);
    Device.vCameraTop.set(top);
    Device.vCameraRight.crossproduct(top, dir);
    Device.mView.build_camera_dir(pos, dir, top);
    Device.mInvView.invert(Device.mView);

    portal_mod_P_std.set(s_proj);
    portal_mod_full_std.mul(portal_mod_P_std, Device.mView);
    ViewBase.CreateFromMatrix(portal_mod_full_std, FRUSTUM_P_LRTB + FRUSTUM_P_FAR);

    // Nothing between the virtual camera and the exit portal may show: the near plane becomes the portal plane.
    Fvector n_view, p_world, p_view;
    Device.mView.transform_dir(n_view, clip.n);
    p_world.mul(clip.n, -clip.d);
    Device.mView.transform_tiny(p_view, p_world);
    Fvector4 C;
    C.set(n_view.x, n_view.y, n_view.z, -n_view.dotproduct(p_view));
    portal_mod_P_obl.set(s_proj);
    portal_mod_make_oblique(portal_mod_P_obl, C);

    portal_mod_projection(false);
    SetCacheXformOld(Device.mView, Device.mProject);

    portal_mod_pass = true;
    r_main.calculate_static();
    Calculate();
    Render();
    portal_mod_pass = false;

    // The main pass must find this frame fresh: lights not added yet, accumulator and flares not cleared yet.
    r_main.sync();
    for (light* L : Lights.package.v_point)
        L->frame_render = 0;
    for (light* L : Lights.package.v_spot)
        L->frame_render = 0;
    for (light* L : Lights.package.v_shadowed)
        L->frame_render = 0;
    Target->portal_mod_reset_marks();
    get_imm_context().reset();

    Device.vCameraPosition.set(s_pos);
    Device.vCameraDirection.set(s_dir);
    Device.vCameraTop.set(s_top);
    Device.vCameraRight.set(s_right);
    Device.mView.set(s_view);
    Device.mInvView.set(s_inv_view);
    Device.mProject.set(s_proj);
    Device.mFullTransform.set(s_full);
    Device.mInvFullTransform.set(s_inv_full);
    ViewBase = s_base;
    SetCacheXform(Device.mView, Device.mProject);
    SetCacheXformOld(Device.mView_old, Device.mProject_old);

    r_main.calculate_static();
}
'''
    p.write_bytes(s.encode("utf-8") + code.replace("\n", nl).encode("utf-8"))
    print("appended RenderPortalView to r4_R_render.cpp")

patch("xrGame/Level.cpp", [
    ("void CLevel::OnRender()\n{\n    inherited::OnRender();\n", "replace", r'''// portal-mod E2: render the view through the linked portal the camera looks at (xr_3da/Render.h portal_mod_draw).
static void portal_mod_render_view()
{
    portal_mod_draw[0].params.w = 0.f;
    portal_mod_draw[1].params.w = 0.f;
    if (!portal_mod_draw[0].on || !portal_mod_draw[1].on || portal_mod_draw[0].params.y < 0.5f)
        return;

    int entry = -1;
    float best = -2.f;
    for (int i = 0; i < 2; ++i)
    {
        const Fmatrix& X = portal_mod_draw[i].xform;
        Fvector to;
        to.sub(X.c, Device.vCameraPosition);
        const float dist = to.magnitude();
        if (dist < EPS_L || to.dotproduct(X.k) >= 0.f)
            continue; // the camera is behind this portal
        to.div(dist);
        const float facing = to.dotproduct(Device.vCameraDirection);
        if (facing < 0.3f && dist > 2.5f)
            continue; // off screen
        if (facing > best)
        {
            best = facing;
            entry = i;
        }
    }
    if (entry < 0)
        return;

    const Fmatrix& A = portal_mod_draw[entry].xform;
    const Fmatrix& B = portal_mod_draw[1 - entry].xform;
    Fvector rA, uA, rB, uB;
    rA.normalize(A.i);
    uA.normalize(A.j);
    rB.normalize(B.i);
    uB.normalize(B.j);
    const Fvector& nA = A.k;
    const Fvector& nB = B.k;
    // into A, out of B: a half turn about the portal's up axis
    auto map_dir = [&](const Fvector& v) {
        Fvector r;
        r.mul(rB, -v.dotproduct(rA)).mad(uB, v.dotproduct(uA)).mad(nB, -v.dotproduct(nA));
        return r;
    };
    Fvector rel;
    rel.sub(Device.vCameraPosition, A.c);
    Fvector pos;
    pos.add(B.c, map_dir(rel));
    const Fvector dir = map_dir(Device.vCameraDirection), top = map_dir(Device.vCameraTop);
    Fvector on_plane;
    on_plane.mad(B.c, nB, 0.03f); // a few cm in front of the exit wall, so the wall itself is cut away
    Fplane clip;
    clip.build(on_plane, nB);
    Render->RenderPortalView(pos, dir, top, clip);
    portal_mod_draw[entry].params.w = 1.f;
}

void CLevel::OnRender()
{
    inherited::OnRender();

    portal_mod_render_view(); // portal-mod E2
'''),
])
