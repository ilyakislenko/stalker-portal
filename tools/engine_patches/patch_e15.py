"""portal-mod engine patch E15: a teleported character forgets where it was.

Every collision geom of the physics character (wheel, hat, shell, cap) keeps the tri-collider's memory of the last
step: last_pos (the back-trajectory test casts from it for tunnelling), the cached triangles around it (last_aabb_*,
cashed_tries) and the triangle it was found behind (neg_tri, b_neg_tri). CPHSimpleCharacter::SetPosition reset only
the pushing flags, so after a portal jump (E12 portal_mod_place, set_actor_position, an NPC through a portal) the
first step saw a trajectory from the entry portal to the exit and the triangles of the entry: the walls on the way
(the portal's own wall among them) pushed the body out of nowhere, held it in the air, or let it through real walls.
Bodies through a portal already get this reset (Level.cpp, the shell teleport); now the character does too. Every
SetPosition caller is a teleport (spawn, vehicle exit, monster and script teleports, portals), none runs per frame.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E15"


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


patch("xrGame/PHSimpleCharacter.cpp", [
    ("    dGeomGetUserData(m_geom_shell)->pushing_neg = false;\n"
     "    dGeomGetUserData(m_hat)->pushing_neg = false;\n", "after",
     "    // portal-mod E15: a teleport, so the collider's memory of the old place goes (last position, cached\n"
     "    // triangles, the triangle it was behind); else the first step collides along the jump\n"
     "    dGeomID geoms[] = {m_wheel, m_hat, m_geom_shell, m_cap};\n"
     "    for (dGeomID g : geoms)\n"
     "    {\n"
     "        if (!g || !dGeomGetUserData(g))\n"
     "            continue;\n"
     "        dGeomUserDataResetLastPos(g);\n"
     "        dGeomUserDataClearCashedTries(g);\n"
     "        dxGeomUserData* d = dGeomGetUserData(g);\n"
     "        d->neg_tri = d->b_neg_tri = NULL;\n"
     "        d->pushing_neg = d->pushing_b_neg = false;\n"
     "    }\n"),
])
