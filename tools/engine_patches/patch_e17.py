"""portal-mod engine patch E17: out of a portal at speed the player flies instead of being stopped at a run.

The character controller (CPHSimpleCharacter) cuts the velocity to the running speed in every physics step while it is
"in control" (touching the ground with a movement key held), and with no key held the ground friction stops it. Out of
a wall portal standing on the floor the feet touch the floor in the first step, so a fall into a floor portal came out
of the wall at a walk. Lua level.portal_fly_actor(v) sets the exit velocity and, when it is faster than a run, keeps the
character flying (b_lose_control) until it is down to a run; on the ground meanwhile it skids, losing about 3/s of its
horizontal speed (like Portal 2: you shoot out of the wall and slide to a stop).
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E17"


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


patch("xrGame/PHSimpleCharacter.h", [
    ("    dReal m_friction_factor;\n", "after",
     "    bool m_portal_fly = false; // portal-mod E17: out of a portal faster than a run, flying until down to a run\n"),
    ("    CPHSimpleCharacter();\n", "after",
     "    void portal_mod_fly(const Fvector& v); // portal-mod E17\n"),
])

patch("xrGame/PHSimpleCharacter.cpp", [
    ("void CPHSimpleCharacter::doCaptureExist(bool& do_exist)", "before",
     "// portal-mod E17: out of a portal with velocity v; faster than a run it flies (see PhDataUpdate)\n"
     "void CPHSimpleCharacter::portal_mod_fly(const Fvector& v)\n"
     "{\n"
     "    if (!b_exist)\n"
     "        return;\n"
     "    Enable();\n"
     "    SetVelocity(v);\n"
     "    const float run = _max(m_max_velocity / phTimefactor, 5.f) * 1.25f;\n"
     "    if (v.square_magnitude() > run * run)\n"
     "    {\n"
     "        b_lose_control = true;\n"
     "        b_jump = false;\n"
     "        m_portal_fly = true;\n"
     "    }\n"
     "}\n"
     "\n"),
    ("    if (b_jumping && b_good_graund || (m_elevator_state.ClimbingState() && b_valide_wall_contact))", "before",
     "    // portal-mod E17: out of a portal faster than a run it keeps flying (touching the ground would give the control\n"
     "    // back and the controller cuts the speed to a run at once); on the ground it skids down to a run\n"
     "    if (m_portal_fly)\n"
     "    {\n"
     "        const float run = _max(m_max_velocity / phTimefactor, 5.f) * 1.25f;\n"
     "        if (m_elevator_state.ClimbingState() || linear_vel_smag < run * run)\n"
     "            m_portal_fly = false;\n"
     "        else\n"
     "        {\n"
     "            b_lose_control = true;\n"
     "            if (b_on_ground)\n"
     "            {\n"
     "                const dReal k = 1.f - 3.f * fixed_step;\n"
     "                dBodySetLinearVel(m_body, velocity[0] * k, velocity[1], velocity[2] * k);\n"
     "            }\n"
     "        }\n"
     "    }\n"
     "\n"),
])

patch("xrGame/level_script.cpp", [
    ('#include "PHMovementControl.h"\n', "after",
     '#include "PHSimpleCharacter.h" // portal-mod E17\n'),
    ("static void set_actor_velocity(Fvector v)\n", "before",
     "static void portal_fly_actor(Fvector v) // portal-mod E17: out of a portal at speed (flies, see CPHSimpleCharacter)\n"
     "{\n"
     "    if (CActor* a = Actor())\n"
     "        if (auto* ch = dynamic_cast<CPHSimpleCharacter*>(a->character_physics_support()->movement()->PHCharacter()))\n"
     "            ch->portal_mod_fly(v);\n"
     "}\n"
     "\n"),
    ('def("portal_set_actor_position", &portal_set_actor_position),', "replace",
     'def("portal_set_actor_position", &portal_set_actor_position), def("portal_fly_actor", &portal_fly_actor),'),
])
