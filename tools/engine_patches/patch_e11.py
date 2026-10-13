"""portal-mod engine patch E11: no glue inside a portal's hole.

When a body's geom is behind a static triangle, the tri-list collider flags it "pushing_neg" and every contact of
that geom gets infinite friction (CollideIntoGroup), so it cannot slide while it is pushed back out. A character
walking into a portal is behind the wall on purpose: its ground contacts got infinite friction and it stuck in the
portal. The flag is ignored for bodies inside a portal's hole zone (portal_mod::in_hole).
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E11"


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


IN_HOLE = """
// portal-mod E11: is a point (a body's centre) in a linked portal's hole zone: over its rectangle (0.2 m more at the
// bottom of a wall portal), from 1 m in front of it to 2 m behind it?
inline bool in_hole(const float* p)
{
    if (!linked())
        return false;
    for (int i = 0; i < 2; ++i)
    {
        Frame A;
        if (!get_frame(i, A))
            continue;
        Fvector q;
        q.set(p[0] - A.c.x, p[1] - A.c.y, p[2] - A.c.z);
        const float h = q.dotproduct(A.n), y = q.dotproduct(A.u);
        if (h < 1.f && h > -2.f && _abs(q.dotproduct(A.r)) < A.hw && y < A.hh && y > -A.hh - (_abs(A.n.y) < 0.7f ? 0.2f : 0.f))
            return true;
    }
    return false;
}

"""

patch("xrGame/portal_mod.h", [
    ("// portal-mod E10: roll added", "before", IN_HOLE),
])

NO_GLUE = ("            if (pushing_neg && dGeomGetBody({g}) && portal_mod::in_hole(dBodyGetPosition(dGeomGetBody({g}))))\n"
           "                pushing_neg = false; // portal-mod E11: behind the wall inside a portal's hole on purpose\n")
patch("xrGame/ActorCameraCollision.cpp", [
    ("    if (!(dGeomGetBody(c.geom.g1) && dGeomGetBody(c.geom.g2)) && portal_mod::hole(c.geom.pos, c.geom.normal))\n        return;\n",
     "replace",
     "    if (!(dGeomGetBody(c.geom.g1) && dGeomGetBody(c.geom.g2)))\n"
     "    {\n"
     "        // portal-mod E11: while the camera is in a portal's hole zone it does not collide with static geometry at all,\n"
     "        // so walking in near the portal's edge the eye still goes in with the body\n"
     "        const dBodyID cam_body = dGeomGetBody(bo1 ? c.geom.g1 : c.geom.g2);\n"
     "        if (portal_mod::hole(c.geom.pos, c.geom.normal) || (cam_body && portal_mod::in_hole(dBodyGetPosition(cam_body))))\n"
     "            return;\n"
     "    }\n"),
])

patch("xrGame/PHSimpleCharacter.cpp", [
    ("    center.y += m_radius + CHWON_CALL_UP_SHIFT;\n", "after",
     "    // portal-mod E11: a portal's hole ahead is an opening, not a wall to stop at or a step to climb (the climb force\n"
     "    // follows the last wall contact's normal and shoved the body sideways along the portal's wall)\n"
     "    if (portal_mod::in_hole(&center.x) || portal_mod::in_hole(&center_forbid.x))\n"
     "        return false;\n"),
])

patch("xrGame/Physics.cpp", [
    ('#include "ExtendedGeom.h"\n', "after", '#include "portal_mod.h" // portal-mod E11\n'),
    ("            pushing_neg = usr_data_2->pushing_b_neg || usr_data_2->pushing_neg;\n", "after", NO_GLUE.format(g="g2")),
    ("            pushing_neg = usr_data_1->pushing_b_neg || usr_data_1->pushing_neg;\n", "after", NO_GLUE.format(g="g1")),
])
