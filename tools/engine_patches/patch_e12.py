"""portal-mod engine patch E12: put the player through a portal without collision correction.

set_actor_position (ForceTransform -> set_movement_position) runs CollisionCorrectObjPos: an activation box is pushed
out of everything it overlaps. Coming out of a portal the body is half inside the exit wall (a hole for it) and the
ground there may be a few centimetres off; the box got shoved up to 0.5 m forward, a visible jump. Lua
level.portal_set_actor_position(pos) places the actor like script set_npc_position(pos, true) does for NPCs: XFORM,
the movement position, the physics character enabled, the stair-step camera smoothing reset. The character's own
contacts settle the feet on the ground.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E12"


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


patch("xrGame/Actor.h", [
    ("    void ForceTransform(const Fmatrix& m) override;\n", "after",
     "    void portal_mod_place(const Fvector& p); // portal-mod E12: teleport with no collision correction\n"),
])

patch("xrGame/Actor.cpp", [
    ("void CActor::ForceTransformAndDirection(const Fmatrix& m)\n", "before",
     "// portal-mod E12: out of a portal the body is half inside the exit wall (a hole for it); the activation box of\n"
     "// set_movement_position would shove it out. The character's own contacts settle the feet on the ground.\n"
     "void CActor::portal_mod_place(const Fvector& p)\n"
     "{\n"
     "    if (!g_Alive())\n"
     "        return;\n"
     "    XFORM().c.set(p);\n"
     "    CPHMovementControl* mc = character_physics_support()->movement();\n"
     "    if (mc->CharacterExist())\n"
     "        mc->EnableCharacter();\n"
     "    mc->SetPosition(p);\n"
     "    fPrevCamPos = p.y;\n"
     "}\n"
     "\n"),
])

patch("xrGame/level_script.cpp", [
    ("static void set_actor_velocity(Fvector v)\n", "before",
     "static void portal_set_actor_position(Fvector p) // portal-mod E12\n"
     "{\n"
     "    if (CActor* a = Actor())\n"
     "        a->portal_mod_place(p);\n"
     "}\n"
     "\n"),
    ('def("actor_velocity", &actor_velocity),', "replace",
     'def("actor_velocity", &actor_velocity), def("portal_set_actor_position", &portal_set_actor_position),'),
])
