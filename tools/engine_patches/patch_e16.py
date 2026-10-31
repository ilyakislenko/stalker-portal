"""portal-mod engine patch E16: the camera box forgets the triangle it was behind when the actor is teleported.

The first-person camera collision (ActorCameraCollision.cpp) is one physics shell put where the eye is every frame and
pushed out of what it overlaps. Going into a portal the box goes behind the wall (or floor) plane inside the hole, and
the tri-collider marks it as behind that triangle (neg_tri, pushing_neg). Nobody cleared that for the camera after the
jump: out of the other portal, wherever the eye was still behind the entry wall's (infinite) plane, every frame the box
was "pushed out" towards it and the eye ended up away from the body - the view knee-deep, walls hit where none were
seen, and the portals stopped taking the player (travel goes by the eye crossing a portal, the eye was somewhere
else). The character itself has this reset in SetPosition; now a teleport of the actor (portal_mod_place, ForceTransform
of set_actor_position) resets the camera shell's geoms the same way, as Level.cpp does for bodies through portals.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E16"


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


patch("xrGame/ActorCameraCollision.cpp", [
    ('#include "GeometryBits.h"\n', "after",
     '#include "Geometry.h" // portal-mod E16\n'
     '#include "ExtendedGeom.h" // portal-mod E16\n'),
    ("void update_current_entity_camera_collision(CPhysicsShellHolder* l_actor)\n", "before",
     "// portal-mod E16: the actor was teleported; the camera box's collider memory (the triangle it was behind, pushing\n"
     "// out of it, the cached triangles) stays at the old place, else the box is pushed towards a wall there every frame\n"
     "void portal_mod_camera_forget()\n"
     "{\n"
     "    if (!actor_camera_shell)\n"
     "        return;\n"
     "    for (CPhysicsElement* el : actor_camera_shell->Elements())\n"
     "    {\n"
     "        for (u16 g = 0; g < el->numberOfGeoms(); ++g)\n"
     "        {\n"
     "            CODEGeom* G = el->geometry(g);\n"
     "            if (!G || !G->geometry_transform())\n"
     "                continue;\n"
     "            dGeomID gid = G->geom();\n"
     "            if (!gid)\n"
     "                gid = G->geometry_transform();\n"
     "            if (!dGeomGetUserData(gid))\n"
     "                continue;\n"
     "            dGeomUserDataResetLastPos(gid);\n"
     "            dGeomGetUserData(gid)->pushing_neg = false;\n"
     "            dGeomGetUserData(gid)->pushing_b_neg = false;\n"
     "            G->clear_cashed_tries();\n"
     "        }\n"
     "    }\n"
     "}\n"
     "\n"),
])

patch("xrGame/Actor.cpp", [
    ("void CActor::ForceTransform(const Fmatrix& m)\n", "before",
     "void portal_mod_camera_forget(); // portal-mod E16 (ActorCameraCollision.cpp)\n"
     "\n"),
    ("    fPrevCamPos = m.c.y; // portal-mod E10: no stair-step camera smoothing after a teleport (it dipped the view)\n",
     "after",
     "    portal_mod_camera_forget(); // portal-mod E16: the camera box forgets the old place too\n"),
    ("    mc->SetPosition(p);\n"
     "    fPrevCamPos = p.y;\n", "after",
     "    portal_mod_camera_forget(); // portal-mod E16\n"),
])
