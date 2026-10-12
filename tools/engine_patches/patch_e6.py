"""portal-mod engine patch E6: fix a crash in the portal pass (E2).

E2 switched to the standard projection around the sky and clouds with portal_mod_projection(), which calls
SetCacheXform() -> set_xform_view/project on EVERY render context. In the middle of Render() other contexts are in use
by worker threads (lights, shadows), so this raced with them: dx10ConstantBuffer::set on a constant table that another
thread had just changed (seen once, at a weapon switch, as c0000005 in R_xforms::set_V under CRender::Render).
Mid-pass switches now change only the projection of the command list that draws the sky/clouds and leave Device and
the other contexts alone.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E6"


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
        anchor, text = anchor.replace("\n", nl), text.replace("\n", nl)
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


patch("Layers/xrRenderPC_R4/r4.h", [
    ("    void portal_mod_projection(bool standard);\n", "replace",
     "    void portal_mod_projection(bool standard, CBackend* only = nullptr); // portal-mod E6: `only` = mid-pass switch\n"),
])

patch("Layers/xrRenderPC_R4/r4_R_render.cpp", [
    ("            portal_mod_projection(true);\n        g_pGamePersistent->Environment().RenderSky(cmd_list);\n"
     "        if (portal_mod_pass)\n            portal_mod_projection(false);\n", "replace",
     "            portal_mod_projection(true, &cmd_list); // portal-mod E6: this context only\n"
     "        g_pGamePersistent->Environment().RenderSky(cmd_list);\n"
     "        if (portal_mod_pass)\n            portal_mod_projection(false, &cmd_list);\n"),
    ("void CRender::portal_mod_projection(bool standard)\n{\n", "replace",
     "void CRender::portal_mod_projection(bool standard, CBackend* only)\n{\n"
     "    if (only) // portal-mod E6: mid-pass, other contexts may be drawing on worker threads right now\n"
     "    {\n"
     "        only->set_xform_project(standard ? portal_mod_P_std : portal_mod_P_obl);\n"
     "        return;\n"
     "    }\n"),
])

patch("Layers/xrRenderPC_R4/r4_rendertarget_phase_combine.cpp", [
    ("            RImplementation.portal_mod_projection(true);\n", "replace",
     "            RImplementation.portal_mod_projection(true, &cmd_list); // portal-mod E6: this context only\n"),
    ("            RImplementation.portal_mod_projection(false);\n", "replace",
     "            RImplementation.portal_mod_projection(false, &cmd_list);\n"),
])
