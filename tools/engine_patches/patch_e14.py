"""portal-mod engine patch E14: portal holes only where they belong.

- Portals were never cleared when a level went away (only Lua removed them). After loading a save or changing level
  the old portals stayed in the engine: drawn, and holes in the collision at their old coordinates - falling through
  the ground and getting stuck "not in a portal". ~CLevel clears them (and the view roll).
- hole() takes the moving body's position: the rules apply only while that body is in front of the portal's opening
  (or in it), not to anything that brushes past near a portal.
- At/behind a wall portal's surface the ground under the feet counts as ground on slopes too (walkable, up to 45
  degrees) unless it leans out of the wall like a board's lower edge (|n.portal| >= 0.15); E10 wanted it within
  7 degrees of flat, so walking by a wall portal on a slope could sink you into the ground.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E14"


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
        if n < 1 or (n != 1 and how != "replace_all"):
            raise SystemExit(f"{rel}: anchor found {n} times: {anchor!r}")
        if how == "replace_all":
            s = s.replace(anchor, text)
            continue
        i = s.index(anchor)
        if how == "replace":
            s = s[:i] + text + s[i + len(anchor):]
        else:
            at = i + len(anchor) if how == "after" else i
            s = s[:at] + text + s[at:]
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))
    print("patched", rel)


patch("xrGame/portal_mod.h", [
    ("inline bool hole(const float* p, const float* nrm, float feet_y = FLT_MAX, float depth = 0.f)\n", "replace",
     "inline bool hole(const float* p, const float* nrm, float feet_y = FLT_MAX, float depth = 0.f, const float* body = nullptr)\n"),
    ("        Fvector q;\n        q.set(p[0] - A.c.x, p[1] - A.c.y, p[2] - A.c.z);\n        const float h = q.dotproduct(A.n); // the surface is at -0.012",
     "replace",
     "        if (body) // portal-mod E14: only for a body in front of the opening (or in it), not one passing near the portal\n"
     "        {\n"
     "            Fvector b;\n"
     "            b.set(body[0] - A.c.x, body[1] - A.c.y, body[2] - A.c.z);\n"
     "            const float hb = b.dotproduct(A.n), xb = b.dotproduct(A.r), yb = b.dotproduct(A.u);\n"
     "            if (hb > 1.2f || hb < -2.f || _abs(xb) > A.hw + 0.3f || yb > A.hh + 0.3f || yb < -A.hh - 0.5f)\n"
     "                continue;\n"
     "        }\n"
     "        Fvector q;\n        q.set(p[0] - A.c.x, p[1] - A.c.y, p[2] - A.c.z);\n        const float h = q.dotproduct(A.n); // the surface is at -0.012"),
    ("        else if (_abs(A.n.y) < 0.7f && h > -0.6f && nu > 0.993f && p[1] < feet_y + 0.05f)\n", "replace",
     "        else if (_abs(A.n.y) < 0.7f && h > -0.6f && nu > 0.7f && _abs(nrm[0] * A.n.x + nrm[1] * A.n.y + nrm[2] * A.n.z) < 0.15f &&\n"
     "                 p[1] < feet_y + 0.05f) // portal-mod E14: slopes are ground too, a board's edge leaning out of the wall is not\n"),
])

patch("xrGame/PHSimpleCharacter.cpp", [
    ("        if (portal_mod::hole(&cp.x, c->geom.normal, feet.y, c->geom.depth))\n", "replace",
     "        if (portal_mod::hole(&cp.x, c->geom.normal, feet.y, c->geom.depth, dBodyGetPosition(m_body))) // portal-mod E14\n"),
])

patch("xrGame/ActorCameraCollision.cpp", [
    ("        if (portal_mod::hole(&cp.x, c.geom.normal) || (cam_body && portal_mod::in_hole(dBodyGetPosition(cam_body))))\n", "replace",
     "        if (cam_body && (portal_mod::hole(&cp.x, c.geom.normal, FLT_MAX, 0.f, dBodyGetPosition(cam_body)) ||\n"
     "                         portal_mod::in_hole(dBodyGetPosition(cam_body)))) // portal-mod E14\n"),
])

patch("xrGame/PHActivationShape.cpp", [
    ("    return portal_mod::hole(&cp.x, c.geom.normal);\n", "replace",
     "    return b && portal_mod::hole(&cp.x, c.geom.normal, FLT_MAX, 0.f, dBodyGetPosition(b)); // portal-mod E14\n"),
])

patch("xrGame/Level.cpp", [
    ('    Msg("- Destroying level");\n', "after",
     "    // portal-mod E14: the portals go with the level (Lua starts with none after a load or a level change)\n"
     "    portal_mod_draw[0].on = false;\n"
     "    portal_mod_draw[1].on = false;\n"
     "    portal_mod::view_roll = 0.f;\n"),
])
