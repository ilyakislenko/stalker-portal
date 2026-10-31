"""portal-mod engine patch E19: portals are seen through portals (Portal 2's tunnel).

The see-through pass (E2) skipped the portal draw altogether (`portal_mod_pass || ...`), so looking into one portal the
other was not there. Now the pass draws them as the main view does: the exit one is behind its camera and drops out by
the facing test, the entry one, when it is in the picture, shows last frame's view through it (rt_portal0 still holds
it while the pass renders into rt_Generic_0) - a portal inside a portal, one frame deeper each frame, as in Portal 2,
with no extra pass. Before any view was rendered (the first frame after linking) it is drawn closed (the swirl).
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E19"


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


patch("xr_3da/Render.h", [
    ("ENGINE_API extern bool portal_mod_pass; // portal-mod E2: true while the renderer draws the view through a portal\n",
     "after",
     "ENGINE_API extern bool portal_mod_view_prev; // portal-mod E19: last frame rendered a view through a portal\n"),
])

patch("xr_3da/Render.cpp", [
    ("ENGINE_API bool portal_mod_pass{}; // portal-mod E2\n", "after",
     "ENGINE_API bool portal_mod_view_prev{}; // portal-mod E19\n"),
])

patch("xrGame/Level.cpp", [
    ("    portal_mod_draw[0].params.w = 0.f;\n    portal_mod_draw[1].params.w = 0.f;\n", "before",
     "    // portal-mod E19: rt_portal0 holds last frame's view when one was rendered - the portals the pass draws show it\n"
     "    portal_mod_view_prev = portal_mod_draw[0].params.w > 0.5f || portal_mod_draw[1].params.w > 0.5f;\n"),
])

patch("Layers/xrRenderPC_R4/r4_R_render.cpp", [
    ("            if (portal_mod_pass || !portal.on || !ViewBase.testSphere_dirty(", "replace",
     "            if (!portal.on || !ViewBase.testSphere_dirty("),
    ("            cmd_list.set_c(\"portal_params\", portal.params.x, portal.params.y, portal.params.z, portal.params.w);\n",
     "replace",
     "            // portal-mod E19: through a portal (the pass) the entry one shows last frame's view - Portal 2's tunnel\n"
     "            const float see = portal_mod_pass ? (portal_mod_view_prev ? 1.f : 0.f) : portal.params.w;\n"
     "            cmd_list.set_c(\"portal_params\", portal.params.x, portal.params.y, portal.params.z, see);\n"),
    ("            cmd_list.Render(close ? 12 : 6);\n", "replace",
     "            cmd_list.Render(close && !portal_mod_pass ? 12 : 6);\n"),
])
