"""portal-mod engine patch E8: NPCs, monsters and corpses through portals; things fall into floor portals.

Living NPCs and monsters (main thread, CLevel::OnFrame): their position, AI path and physics character have to move
together, so this is not done on the physics thread. One standing on a floor portal (feet inside the oval) falls in;
one walking into any other portal goes in. It comes out of the other portal upright (on its feet in front of a wall
portal, on top of a floor portal, under a ceiling one) with its velocity turned through the portals; teleported like
script set_npc_position (XFORM + movement SetPosition, detail path made inactual, animation movement dropped).

Physics bodies (physics thread, E4 step): corpses (shells of dead CEntityAlive) are no longer skipped, and a body
resting on or sliding over a floor portal falls in (2 m/s straight down into it), sleeping ones included.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E8"


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


NPC_FRAME = r'''
// portal-mod E8: living NPCs and monsters through portals. Main thread: the AI's position, path and physics character
// move together (as script set_npc_position does).
static void portal_mod_npc_frame()
{
    using namespace portal_mod;
    Frame P[2];
    if (!linked() || !get_frame(0, P[0]) || !get_frame(1, P[1]))
        return;

    static xr_vector<CObject*> near_objects;
    static xr_map<u16, u32> cooldown; // object id -> time before which it may not travel again
    const u32 now = Device.dwTimeGlobal;

    for (int i = 0; i < 2; ++i)
    {
        const Frame& A = P[i];
        const Frame& B = P[1 - i];
        near_objects.clear();
        Level().ObjectSpace.GetNearest(near_objects, A.c, _max(A.hw, A.hh) + 2.5f, nullptr);
        for (CObject* o : near_objects)
        {
            CCustomMonster* m = smart_cast<CCustomMonster*>(o);
            if (!m || !m->g_Alive() || m->H_Parent() || !m->character_physics_support())
                continue;
            CPHMovementControl* mc = m->character_physics_support()->movement();
            if (!mc || !mc->CharacterExist())
                continue;
            auto cd = cooldown.find(m->ID());
            if (cd != cooldown.end() && cd->second > now)
                continue;

            Fvector v;
            mc->GetCharacterVelocity(v);
            const Fvector feet = m->Position();
            const float H = _max(mc->Box().y2 - mc->Box().y1, 0.4f); // body height
            const float fr = _max(mc->FootRadius(), 0.2f);
            Fvector v_in;
            if (A.n.y > 0.7f)
            {
                // floor portal: standing on it (feet inside the oval, room for the body) -> falls in
                Fvector q;
                q.sub(feet, A.c);
                const float d = q.dotproduct(A.n);
                const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;
                if (d < -0.3f || d > 0.4f || x * x + y * y > 0.75f * 0.75f)
                    continue;
                const float down = -v.dotproduct(A.n);
                v_in.mad(v, A.n, down).mad(A.n, -_max(down, 2.5f)); // keep the sideways part, at least 2.5 m/s down
            }
            else
            {
                // wall or ceiling portal: the body's middle goes in
                Fvector c;
                c.mad(feet, Fvector().set(0.f, 1.f, 0.f), H * 0.5f);
                const float vn = -v.dotproduct(A.n);
                if (vn < 0.5f)
                    continue;
                const float d = Fvector().sub(c, A.c).dotproduct(A.n);
                if (d < -fr || d - fr > vn * _max(Device.fTimeDelta, 0.01f) * 2.f + 0.1f)
                    continue;
                Fvector q;
                q.mad(c, v, _max(d, 0.f) / vn).sub(A.c);
                const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;
                if (x * x + y * y > 1.f)
                    continue;
                v_in.set(v);
            }

            // out of B: upright, clear of its surface, moving away from it
            Fvector v_out = map_dir(A, B, v_in);
            Fvector out;
            float away;
            if (B.n.y > 0.7f) // floor: stands on it and pops up
            {
                out.mad(B.c, B.n, 0.05f);
                away = 3.5f;
            }
            else if (B.n.y < -0.7f) // ceiling: hangs below it and drops
            {
                out.set(B.c.x, B.c.y - H - 0.15f, B.c.z);
                away = 0.5f;
            }
            else // wall: on its feet in the oval's middle, in front of it
            {
                out.mad(B.c, B.n, fr + 0.25f);
                out.y -= _min(H * 0.5f, B.hh - 0.05f);
                away = 1.5f;
            }
            const float vb = v_out.dotproduct(B.n);
            if (vb < away)
                v_out.mad(B.n, away - vb);

            Fmatrix F = m->XFORM();
            F.c = out;
            m->XFORM().set(F);
            mc->SetPosition(out);
            mc->SetVelocity(v_out);
            m->movement().detail().make_inactual();
            if (m->animation_movement_controlled())
                m->destroy_anim_mov_ctrl();
            cooldown[m->ID()] = now + 400;
            Msg("[portal_mod] %s went through portal %d at %.1f m/s (npc), out at %.1f m/s", m->cName().c_str(), i,
                v_in.magnitude(), v_out.magnitude());
        }
    }
}
'''

patch("xrGame/Level.cpp", [
    ('#include "PhysicsShellHolder.h"\n#include "entity_alive.h"\n', "after",
     '#include "CustomMonster.h" // portal-mod E8\n#include "CharacterPhysicsSupport.h"\n#include "PHMovementControl.h"\n'
     '#include "movement_manager.h"\n#include "detail_path_manager.h"\n'),
    ("void CLevel::OnFrame()\n{\n", "before", "static void portal_mod_npc_frame(); // portal-mod E8\n\n"),
    ("    ProcessGameEvents();\n", "after", "\n    portal_mod_npc_frame(); // portal-mod E8\n"),
    ("void CLevel::PhisStepsCallback(u32, u32) { portal_mod_physics_step(); }\n", "after", NPC_FRAME),
    # physics bodies: corpses too; a body on a floor portal falls in (sleeping ones too)
    ("            if (!shell || !shell->isActive() || !shell->isEnabled() || shell->Elements().empty())\n"
     "                continue;\n"
     "            CPhysicsShellHolder* holder = shell->get_ElementByStoreOrder(0)->PhysicsRefObject();\n"
     "            if (!holder || holder->H_Parent() || smart_cast<CEntityAlive*>(holder) || smart_cast<CCar*>(holder))\n"
     "                continue;\n",
     "replace",
     "            if (!shell || !shell->isActive() || shell->Elements().empty())\n"
     "                continue;\n"
     "            CPhysicsShellHolder* holder = shell->get_ElementByStoreOrder(0)->PhysicsRefObject();\n"
     "            if (!holder || holder->H_Parent() || smart_cast<CCar*>(holder))\n"
     "                continue;\n"
     "            if (const CEntityAlive* ea = smart_cast<CEntityAlive*>(holder); ea && ea->g_Alive())\n"
     "                continue; // portal-mod E8: living ones go in portal_mod_npc_frame, corpses (ragdolls) here\n"),
    ("            Fvector v;\n"
     "            shell->get_LinearVel(v);\n"
     "            const float vn = -v.dotproduct(A.n); // speed towards the portal\n"
     "            if (vn < 0.3f)\n"
     "                continue;\n"
     "            const Fvector& pos = s->spatial.sphere.P;\n"
     "            const float R = _min(_max(s->spatial.sphere.R, 0.05f), 1.f);\n"
     "            const float d = Fvector().sub(pos, A.c).dotproduct(A.n);\n",
     "replace",
     "            Fvector v;\n"
     "            shell->get_LinearVel(v);\n"
     "            float vn = -v.dotproduct(A.n); // speed towards the portal\n"
     "            const Fvector& pos = s->spatial.sphere.P;\n"
     "            const float R = _min(_max(s->spatial.sphere.R, 0.05f), 1.f);\n"
     "            const float d = Fvector().sub(pos, A.c).dotproduct(A.n);\n"
     "            // portal-mod E8: lying on (or sliding over) a floor portal -> falls in at 2 m/s\n"
     "            if (A.n.y > 0.7f && vn < 2.f && d > -0.05f && d < R + 0.15f)\n"
     "            {\n"
     "                Fvector q;\n"
     "                q.sub(pos, A.c);\n"
     "                const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;\n"
     "                if (x * x + y * y < 0.85f * 0.85f)\n"
     "                {\n"
     "                    const Fvector add = Fvector().mul(A.n, vn - 2.f);\n"
     "                    for (CPhysicsElement* el : shell->Elements())\n"
     "                    {\n"
     "                        Fvector ev;\n"
     "                        el->get_LinearVel(ev);\n"
     "                        el->set_LinearVel(ev.add(add));\n"
     "                    }\n"
     "                    v.add(add);\n"
     "                    vn = 2.f;\n"
     "                    shell->Enable();\n"
     "                }\n"
     "            }\n"
     "            if (vn < 0.3f || !shell->isEnabled())\n"
     "                continue;\n"),
])
