"""portal-mod engine patch E13: test a portal's hole at the real contact point.

The tri-list collider reports, for long triangles, the triangle's far vertex as the contact point: walking into a
portal on a fence, the contacts with its horizontal boards came at points 3.6 and 19 m away, on the fence's plane.
hole() saw them far outside the portal and kept the boards solid; their impulses (applied at those far points) turned
the player's velocity aside by up to 150 degrees in a few steps - stuck at the portal or shoved along the fence.
When the reported point is more than 1.5 m from the body, the body's centre projected onto the contact plane is used.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E13"


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
    ("// portal-mod E10: roll added", "before", """// portal-mod E13: where a contact really is. The tri-list collider reports a long triangle's far vertex as the contact
// point (a 20 m fence board: 20 m away); then the body's centre projected onto the contact plane is used instead.
inline void contact_point(const float* pos, const float* nrm, const float* body, float* out)
{
    const float dx = pos[0] - body[0], dy = pos[1] - body[1], dz = pos[2] - body[2];
    if (dx * dx + dy * dy + dz * dz <= 1.5f * 1.5f)
    {
        out[0] = pos[0];
        out[1] = pos[1];
        out[2] = pos[2];
        return;
    }
    const float d = dx * nrm[0] + dy * nrm[1] + dz * nrm[2];
    out[0] = body[0] + nrm[0] * d;
    out[1] = body[1] + nrm[1] * d;
    out[2] = body[2] + nrm[2] * d;
}

"""),
])

patch("xrGame/PHSimpleCharacter.cpp", [
    ("        if (portal_mod::hole(c->geom.pos, c->geom.normal, feet.y, c->geom.depth))\n", "replace",
     "        Fvector cp; // portal-mod E13: the real contact point\n"
     "        portal_mod::contact_point(c->geom.pos, c->geom.normal, dBodyGetPosition(m_body), &cp.x);\n"
     "        if (portal_mod::hole(&cp.x, c->geom.normal, feet.y, c->geom.depth))\n"),
])

patch("xrGame/ActorCameraCollision.cpp", [
    ("        if (portal_mod::hole(c.geom.pos, c.geom.normal) || (cam_body && portal_mod::in_hole(dBodyGetPosition(cam_body))))\n", "replace",
     "        Fvector cp; // portal-mod E13: the real contact point\n"
     "        if (cam_body)\n"
     "            portal_mod::contact_point(c.geom.pos, c.geom.normal, dBodyGetPosition(cam_body), &cp.x);\n"
     "        else\n"
     "            cp.set(c.geom.pos[0], c.geom.pos[1], c.geom.pos[2]);\n"
     "        if (portal_mod::hole(&cp.x, c.geom.normal) || (cam_body && portal_mod::in_hole(dBodyGetPosition(cam_body))))\n"),
])

patch("xrGame/PHActivationShape.cpp", [
    ('#include "portal_mod.h" // portal-mod E10\n', "after",
     "// portal-mod E13: hole() at the real contact point (the moving body's centre projected when the reported one is far)\n"
     "static bool portal_mod_hole_contact(const dContact& c)\n"
     "{\n"
     "    const dBodyID b = dGeomGetBody(c.geom.g1) ? dGeomGetBody(c.geom.g1) : dGeomGetBody(c.geom.g2);\n"
     "    Fvector cp;\n"
     "    if (b)\n"
     "        portal_mod::contact_point(c.geom.pos, c.geom.normal, dBodyGetPosition(b), &cp.x);\n"
     "    else\n"
     "        cp.set(c.geom.pos[0], c.geom.pos[1], c.geom.pos[2]);\n"
     "    return portal_mod::hole(&cp.x, c.geom.normal);\n"
     "}\n"),
    ("portal_mod::hole(c.geom.pos, c.geom.normal))", "replace_all", "portal_mod_hole_contact(c))"),
])
