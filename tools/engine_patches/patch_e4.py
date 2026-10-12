"""portal-mod engine patch E4: bullets, grenades, rockets and other physics bodies through portals.

Bullets (CBulletManager, worker thread): the step's ray stops at a portal plane it would cross inside the oval; the
bullet then continues out of the other portal with its direction turned the same way, keeping speed, shooter and
weapon (hits on the far side count as the shooter's). The tracer is clipped so it does not stick out of the wall
behind the exit. Portal frames are snapshot on the main thread in CommitRenderSet.

Physics bodies (CLevel::PhisStepsCallback, after every 0.01 s step on the physics thread): a body that would reach a
portal's oval within the next steps is moved out of the other portal (shell->TransformPosition with the portal
transform, pushed out by its radius) with linear and angular velocities mapped, its geoms' last positions reset
(else rockets/grenades "hit" the wall along the swept ray), and a short per-object cooldown.

Rockets: thrust follows the body's own transform instead of XFORM() (updated only on the main thread), so a rocket
keeps flying straight out of the exit portal.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E4"


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


patch("xrGame/Level_Bullet_Manager.h", [
    ('#include "tracer.h"\n', "after", '#include "portal_mod.h" // portal-mod E4\n'),
    ("    float fly_dist; //дистанция которую пуля пролетела\n", "after",
     "    float portal_dist; // portal-mod E4: metres since the bullet last came out of a portal (clips the tracer)\n"),
    ("    BulletVec m_BulletsRendered; // copy for rendering\n", "after",
     "    portal_mod::Frame m_pf[2]; // portal-mod E4: portals as of this frame, for the worker thread\n"
     "    bool m_portals_linked{};\n"),
])

patch("xrGame/Level_Bullet_Manager.cpp", [
    ("    fly_dist = 0;\n", "after", "    portal_dist = FLT_MAX; // portal-mod E4\n"),
    ("    collide::ray_defs RD(bullet->pos, bullet->dir, range, CDB::OPT_CULL, collide::rqtBoth);\n"
     "    BOOL result = FALSE;\n"
     "    VERIFY(!fis_zero(RD.dir.square_magnitude()));\n"
     "    result = Level().ObjectSpace.RayQuery(rq_storage, RD, firetrace_callback, &bullet_data, test_callback, NULL);\n",
     "replace",
     "    // portal-mod E4: a portal on the way? Trace only up to its plane; if nothing is hit before it, go through.\n"
     "    int portal_in = -1;\n"
     "    if (m_portals_linked)\n"
     "    {\n"
     "        for (int i = 0; i < 2 && portal_in < 0; ++i)\n"
     "        {\n"
     "            float t;\n"
     "            if (portal_mod::crosses(m_pf[i], bullet->pos, bullet->dir, range, t))\n"
     "            {\n"
     "                portal_in = i;\n"
     "                range = t;\n"
     "            }\n"
     "        }\n"
     "    }\n"
     "\n"
     "    BOOL result = FALSE;\n"
     "    if (range > EPS_L)\n"
     "    {\n"
     "        collide::ray_defs RD(bullet->pos, bullet->dir, range, CDB::OPT_CULL, collide::rqtBoth);\n"
     "        VERIFY(!fis_zero(RD.dir.square_magnitude()));\n"
     "        result = Level().ObjectSpace.RayQuery(rq_storage, RD, firetrace_callback, &bullet_data, test_callback, NULL);\n"
     "    }\n"),
    ("    if (result && bullet_data.bStopTracing)\n    {\n        range = (rq_storage.r_begin() + rq_storage.r_count() - 1)->range;\n    }\n",
     "after",
     "    else if (portal_in >= 0 && !bullet->flags.ricochet_was) // portal-mod E4: through the portal\n"
     "    {\n"
     "        const portal_mod::Frame& A = m_pf[portal_in];\n"
     "        const portal_mod::Frame& B = m_pf[1 - portal_in];\n"
     "        Fvector at;\n"
     "        at.mad(bullet->pos, cur_dir, range);\n"
     "        bullet->fly_dist += range;\n"
     "        bullet->dir = portal_mod::map_dir(A, B, cur_dir);\n"
     "        bullet->pos = portal_mod::map_point(A, B, at);\n"
     "        bullet->pos.mad(bullet->dir, 0.02f);\n"
     "        cur_dir = bullet->dir;\n"
     "        bullet->portal_dist = 0.f;\n"
     "        range = 0.f;\n"
     "    }\n"),
    ("        bullet->pos.mad(bullet->pos, cur_dir, range);\n        bullet->fly_dist += range;\n", "after",
     "        bullet->portal_dist += range; // portal-mod E4\n"),
    ("        if (length > m_fTracerLengthMax)\n            length = m_fTracerLengthMax;\n", "after",
     "        if (length > bullet.portal_dist) // portal-mod E4: no tracer sticking out of the wall behind the exit portal\n"
     "            length = bullet.portal_dist;\n"
     "        if (length < m_fTracerLengthMin)\n"
     "            continue;\n"),
    ("    m_BulletsRendered = m_Bullets;\n", "after",
     "    // portal-mod E4: the worker thread reads the portals from here, not from what Lua may change meanwhile\n"
     "    m_portals_linked = portal_mod::linked() && portal_mod::get_frame(0, m_pf[0]) && portal_mod::get_frame(1, m_pf[1]);\n"),
])

patch("xrGame/CustomRocket.cpp", [
    ("    l_dir.set(XFORM().k);\n", "replace",
     "    { // portal-mod E4: thrust along the body as it is now (XFORM() lags a frame; after a portal it points the old way)\n"
     "        Fmatrix body;\n"
     "        m_pPhysicsShell->GetGlobalTransformDynamic(&body);\n"
     "        l_dir.set(body.k);\n"
     "    }\n"),
])

patch("xrGame/Level.cpp", [
    ('#include "car.h"\n', "after",
     '#include "portal_mod.h" // portal-mod E4\n#include "PHShell.h"\n#include "PHObject.h"\n#include "Geometry.h"\n'
     '#include "ExtendedGeom.h"\n#include "PhysicsShellHolder.h"\n#include "entity_alive.h"\n'),
    ("void CLevel::PhisStepsCallback(u32, u32) {}\n", "replace", r'''// portal-mod E4: physics bodies through portals (grenades, rockets, bolts, dropped items, ragdolls). Runs after every
// physics step (0.01 s) on the physics thread: a body that would reach a portal's oval within the next steps leaves
// the other portal with its velocities turned the same way, before it can touch the wall behind the portal.
static void portal_mod_teleport_shell(CPhysicsShell* shell, const portal_mod::Frame& A, const portal_mod::Frame& B, float push)
{
    using namespace portal_mod;
    Fmatrix form;
    form.identity();
    form.i = map_dir(A, B, Fvector().set(1.f, 0.f, 0.f));
    form.j = map_dir(A, B, Fvector().set(0.f, 1.f, 0.f));
    form.k = map_dir(A, B, Fvector().set(0.f, 0.f, 1.f));
    form.c = map_point(A, B, Fvector().set(0.f, 0.f, 0.f));
    form.c.mad(B.n, push);

    ELEMENT_STORAGE& elements = shell->Elements();
    xr_vector<std::pair<Fvector, Fvector>> vel(elements.size());
    for (size_t e = 0; e < elements.size(); ++e)
    {
        elements[e]->get_LinearVel(vel[e].first);
        elements[e]->get_AngularVel(vel[e].second);
    }
    shell->TransformPosition(form);
    for (size_t e = 0; e < elements.size(); ++e)
    {
        CPhysicsElement* el = elements[e];
        el->set_LinearVel(map_dir(A, B, vel[e].first));
        el->set_AngularVel(map_dir(A, B, vel[e].second));
        // forget where it was: rockets and grenades sweep a ray from the last position and would hit the wall
        for (u16 g = 0; g < el->numberOfGeoms(); ++g)
        {
            CODEGeom* G = el->geometry(g);
            if (!G || !G->geometry_transform())
                continue;
            dGeomID gid = G->geom();
            if (!gid)
                gid = G->geometry_transform();
            dGeomUserDataResetLastPos(gid);
            dGeomGetUserData(gid)->pushing_neg = false;
            dGeomGetUserData(gid)->pushing_b_neg = false;
            G->clear_cashed_tries();
        }
    }
    shell->Enable();
}

static void portal_mod_physics_step()
{
    using namespace portal_mod;
    Frame P[2];
    if (!linked() || !get_frame(0, P[0]) || !get_frame(1, P[1]))
        return;

    static xr_vector<ISpatial*> found;
    static xr_map<u16, u32> cooldown; // object id -> step before which it may not travel again
    static u32 step = 0;
    ++step;

    for (int i = 0; i < 2; ++i)
    {
        const Frame& A = P[i];
        const Frame& B = P[1 - i];
        const float reach = _max(A.hw, A.hh) + 2.f;
        found.clear();
        g_SpatialSpacePhysic->q_box(found, 0, STYPE_PHYSIC, A.c, Fvector().set(reach, reach, reach));
        for (ISpatial* s : found)
        {
            CPHObject* ph = static_cast<CPHObject*>(s);
            if (ph->CastType() == CPHObject::tpCharacter)
                continue;
            CPHShell* shell = smart_cast<CPHShell*>(ph);
            if (!shell || !shell->isActive() || !shell->isEnabled() || shell->Elements().empty())
                continue;
            CPhysicsShellHolder* holder = shell->get_ElementByStoreOrder(0)->PhysicsRefObject();
            if (!holder || holder->H_Parent() || smart_cast<CEntityAlive*>(holder) || smart_cast<CCar*>(holder))
                continue;
            auto cd = cooldown.find(holder->ID());
            if (cd != cooldown.end() && cd->second > step)
                continue;

            Fvector v;
            shell->get_LinearVel(v);
            const float vn = -v.dotproduct(A.n); // speed towards the portal
            if (vn < 0.3f)
                continue;
            const Fvector& pos = s->spatial.sphere.P;
            const float R = _min(_max(s->spatial.sphere.R, 0.05f), 1.f);
            const float d = Fvector().sub(pos, A.c).dotproduct(A.n);
            if (d < -R || d - R > vn * fixed_step * 3.f + 0.05f)
                continue; // behind it, or not there within the next steps
            Fvector q;
            q.mad(pos, v, _max(d, 0.f) / vn).sub(A.c); // where it meets the portal plane
            const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;
            if (x * x + y * y > 1.f)
                continue;

            portal_mod_teleport_shell(shell, A, B, _max(d, 0.f) + R + 0.05f);
            cooldown[holder->ID()] = step + 20;
            Msg("[portal_mod] %s went through portal %d at %.1f m/s", holder->cName().c_str(), i, v.magnitude());
        }
    }
}

void CLevel::PhisStepsCallback(u32, u32) { portal_mod_physics_step(); }
'''),
])
