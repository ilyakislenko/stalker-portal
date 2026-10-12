"""portal-mod engine patch E1: Portal 2 portals drawn in the R4 forward pass + Lua API.

Adds (on branch portal-mod of E:/github/OGSR-Engine):
  xr_3da/Render.h, Render.cpp       PORTAL_MOD_DRAW portal_mod_draw[2]  (what the renderer draws)
  r4_rendertarget.h/.cpp            ref_shader s_portal_gun = "effects_portal_gun" (gamedata/shaders/r3/effects_portal_gun.s)
  r4_R_render.cpp render_forward    draws each active portal as a 6-vertex quad (vertex-id quad, like puddles)
  xrGame/level_script.cpp           level.portal_set / portal_clear / ray_query_normal / actor_velocity / set_actor_velocity
Idempotent: skips a file that already has the marker. Keeps each file's line endings.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod"


def patch(rel, edits):
    p = ENG / rel
    raw = p.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    if MARK in s:
        print("skip (already patched)", rel)
        return
    nl = "\r\n" if "\r\n" in s else "\n"
    for anchor, where, text in edits:
        anchor = anchor.replace("\n", nl)
        text = text.replace("\n", nl)
        n = s.count(anchor)
        if n != 1:
            raise SystemExit(f"{rel}: anchor found {n} times: {anchor!r}")
        i = s.index(anchor)
        at = i + len(anchor) if where == "after" else i
        s = s[:at] + text + s[at:]
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))
    print("patched", rel)


patch("xr_3da/Render.h", [(
    "ENGINE_API extern GRASS_SHADER_DATA_OLD grass_shader_data_old;\n", "after", """
// portal-mod: Portal 2 portals drawn by the renderer's forward pass; filled from Lua (level.portal_set/portal_clear)
struct PORTAL_MOD_DRAW
{
    bool on{};
    Fmatrix xform{}; // i = right * half width, j = up * half height, k = surface normal, c = centre
    Fvector4 params{}; // x: 0 blue / 1 orange, y: 1 = linked (shows the other side), z: open 0..1, w: reserved
};
ENGINE_API extern PORTAL_MOD_DRAW portal_mod_draw[2];
""")])

patch("xr_3da/Render.cpp", [(
    "ENGINE_API GRASS_SHADER_DATA_OLD grass_shader_data_old{};\n", "after",
    "ENGINE_API PORTAL_MOD_DRAW portal_mod_draw[2]{}; // portal-mod\n")])

patch("Layers/xrRenderPC_R4/r4_rendertarget.h", [(
    "    ref_shader s_puddles;\n", "after",
    "    ref_shader s_portal_gun; // portal-mod\n")])

patch("Layers/xrRenderPC_R4/r4_rendertarget.cpp", [(
    '    s_puddles.create("effects_water_puddles");\n', "after",
    '    s_portal_gun.create("effects_portal_gun"); // portal-mod: gamedata/shaders/r3/effects_portal_gun.s\n')])

patch("Layers/xrRenderPC_R4/r4_R_render.cpp", [(
    "        dsgraph.r_dsgraph_render_graph(1); // normal level, secondary priority\n", "before",
    """        // portal-mod: Portal 2 portals (xr_3da/Render.h portal_mod_draw, set from Lua by level.portal_set)
        for (const auto& portal : portal_mod_draw)
        {
            if (!portal.on || !ViewBase.testSphere_dirty(portal.xform.c, std::max(portal.xform.i.magnitude(), portal.xform.j.magnitude())))
                continue;

            cmd_list.set_Shader(Target->s_portal_gun);
            cmd_list.set_xform_world(portal.xform);
            cmd_list.set_c("portal_params", portal.params.x, portal.params.y, portal.params.z, portal.params.w);

            cmd_list.Render(6);
        }

""")])

patch("xrGame/level_script.cpp", [
    ('#include "LevelDebugScript.h"\n', "after", '''#include "CharacterPhysicsSupport.h" // portal-mod
#include "PHMovementControl.h"

// portal-mod: Lua side of the Portal 2 portals and the actor's velocity (momentum through portals)
static void portal_set(int idx, Fvector pos, Fvector normal, Fvector up, float w, float h, float color, bool linked, float open)
{
    if (idx < 0 || idx > 1)
        return;
    Fvector n = normal, u = up, r;
    n.normalize_safe();
    u.normalize_safe();
    r.crossproduct(u, n).normalize_safe();
    PORTAL_MOD_DRAW& p = portal_mod_draw[idx];
    p.xform.identity();
    p.xform.i.mul(r, w * 0.5f);
    p.xform.j.mul(u, h * 0.5f);
    p.xform.k.set(n);
    p.xform.c.mad(pos, n, 0.012f); // a centimetre off the wall: no z-fighting
    p.params.set(color, linked ? 1.f : 0.f, open, 0.f);
    p.on = true;
}

static void portal_clear(int idx)
{
    if (idx >= 0 && idx <= 1)
        portal_mod_draw[idx].on = false;
}

// Normal of the static triangle a ray hits (facing the ray), or (0,0,0) if it hits nothing static.
static Fvector ray_query_normal(Fvector start, Fvector dir, float range)
{
    Fvector res{};
    collide::rq_result RQ;
    CObject* ignore = Level().CurrentEntity();
    if (Level().ObjectSpace.RayPick(start, dir, range, collide::rqtStatic, RQ, ignore) && !RQ.O)
    {
        const CDB::TRI& t = Level().ObjectSpace.GetStaticTris()[RQ.element];
        const Fvector* v = Level().ObjectSpace.GetStaticVerts();
        Fvector e1, e2;
        e1.sub(v[t.verts[1]], v[t.verts[0]]);
        e2.sub(v[t.verts[2]], v[t.verts[0]]);
        res.crossproduct(e1, e2).normalize_safe();
        if (res.dotproduct(dir) > 0.f)
            res.invert();
    }
    return res;
}

static Fvector actor_velocity()
{
    Fvector v{};
    if (CActor* a = Actor())
        v.set(a->character_physics_support()->movement()->GetVelocity());
    return v;
}

static void set_actor_velocity(Fvector v)
{
    if (CActor* a = Actor())
        a->character_physics_support()->movement()->SetVelocity(v);
}
'''),
    ('            def("get_target_dist", &GetTargetDist),', "before",
     '''            def("portal_set", &portal_set), def("portal_clear", &portal_clear), def("ray_query_normal", &ray_query_normal), // portal-mod
            def("actor_velocity", &actor_velocity), def("set_actor_velocity", &set_actor_velocity),

'''),
])
