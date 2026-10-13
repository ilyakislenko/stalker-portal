"""portal-mod engine patch E10: walking into portals like in Portal 2.

- A linked portal is a hole for characters: contacts of the actor/NPC physics character with static geometry inside
  the portal's oval are dropped: anything behind the surface (up to 2.5 m: the wall, steps or floors inside a house
  behind it) and the surface itself in front of it. The same for the first-person camera's collision box, so the eye
  goes in with the body. The player can step into a wall portal, stand half inside it, and falls into a floor portal.
- Portals are drawn with a second, larger quad 0.5 m behind the surface. Normally the wall hides it; when the camera
  is closer than the near plane (0.2 m) and the front quad and the wall are both clipped away, it keeps the view
  through the portal on screen instead of whatever lies behind the wall. (Shader: portal_gun.vs, 12 vertices.)
- CActor::ForceTransform resets the stair-step camera smoothing: after a teleport upwards the view used to start up
  to 0.2 m low and catch up.
- level.portal_view_roll(radians): a roll added to the first-person camera. After a portal turns the player's view
  (floor/ceiling portals) Lua sets it and brings it back to 0, like Portal 2 straightening the view.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E10"


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


patch("xrGame/portal_mod.h", [
    ("} // namespace portal_mod\n", "before", r'''
// portal-mod E10: a character's contact with static geometry at p (contact normal nrm) inside a linked portal:
// anything at or behind the portal's surface (up to 2.5 m: the wall, frames and bumps in it, whatever is behind it)
// but the ground at its foot, or, in front of it, the surface itself (a sphere's contact point can sit up to its
// radius out, facing along the portal's normal).
// Such contacts are dropped, so the portal is a hole you can walk into (and fall into, on a floor); a floor in front
// of a wall portal still holds you up. depth: the contact's penetration. feet_y (a character's feet): only what is right under them (12 cm) counts as ground,
// not the top or underside of a fence rail or a sill at shin, knee or chest height.
inline bool hole(const float* p, const float* nrm, float feet_y = FLT_MAX, float depth = 0.f)
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
        const float h = q.dotproduct(A.n); // the surface is at -0.012 (the drawn quad floats 1.2 cm in front)
        if (h > 0.6f || h < -2.5f)
            continue;
        const float nu = _abs(nrm[0] * A.u.x + nrm[1] * A.u.y + nrm[2] * A.u.z);
        if (h > 0.3f)
        {
            if (_abs(nrm[0] * A.n.x + nrm[1] * A.n.y + nrm[2] * A.n.z) < 0.5f)
                continue; // further out only the surface itself (a sphere's contact point sits at its centre)
        }
        else if (h > 0.05f)
        {
            if (nu > 0.7f && p[1] < feet_y + 0.12f)
                continue; // the ground in front holds you up (floor/ceiling portals: whatever stands along them)
        }
        else if (_abs(A.n.y) < 0.7f && h > -0.6f && nu > 0.993f && p[1] < feet_y + 0.05f)
            continue; // flat ground level with the feet at and just behind a wall portal: you walk in on it (with nothing
                      // under the leading foot the character controller backs off as from a ledge). Not a fence's bottom
                      // rail or the boards' lower edge: their contacts are higher or slanted (a board's edge leans
                      // 10-12 degrees, the ground under the feet hardly at all). No depth test: a foot that sank a
                      // little would lose the ground behind the plane and sink further.
        // at or behind the surface anything goes: the wall, frames and bumps in it, steps and floors behind it
        // the hole is the portal's rectangle, as in Portal 2 (the oval is only drawn): an oval's narrow bottom would
        // catch the feet of someone walking into a portal that stands on the floor. A wall portal's hole reaches 0.2 m
        // below it, so a portal a few centimetres above the floor can be walked into like a low step.
        const float y = q.dotproduct(A.u);
        if (_abs(q.dotproduct(A.r)) < A.hw && y < A.hh && y > -A.hh - (_abs(A.n.y) < 0.7f ? 0.2f : 0.f))
            return true;
    }
    return false;
}

// portal-mod E10: roll added to the first-person camera (radians), set from Lua (level.portal_view_roll)
inline float view_roll = 0.f;
'''),
])

patch("xrGame/PHSimpleCharacter.cpp", [
    ('#include "game_base_space.h"\n', "after", '#include "portal_mod.h" // portal-mod E10\n'),
    ("void CPHSimpleCharacter::InitContact(dContact* c, bool& do_collide, u16 material_idx_1, u16 material_idx_2)\n{\n",
     "after",
     "    // portal-mod E10: the surface inside a linked portal is a hole (static geometry only)\n"
     "    if (do_collide && !(dGeomGetBody(c->geom.g1) && dGeomGetBody(c->geom.g2)))\n"
     "    {\n"
     "        Fvector feet;\n"
     "        GetPosition(feet);\n"
     "        if (portal_mod::hole(c->geom.pos, c->geom.normal, feet.y, c->geom.depth))\n"
     "        {\n"
     "            do_collide = false;\n"
     "            return;\n"
     "        }\n"
     "    }\n"),
])

HOLE_CB = ("    if (do_colide && !(dGeomGetBody(c.geom.g1) && dGeomGetBody(c.geom.g2)) && portal_mod::hole(c.geom.pos, c.geom.normal))\n"
           "    {\n"
           "        do_colide = false; // portal-mod E10: a teleport into a portal's hole is not pushed back out of the wall\n"
           "        return;\n"
           "    }\n")
CB = "(bool& do_colide, bool bo1, dContact& c, SGameMtl* material_1, SGameMtl* material_2)\n{\n"
patch("xrGame/PHActivationShape.cpp", [
    ('#include "phnetstate.h"\n', "after", '#include "portal_mod.h" // portal-mod E10\n'),
    ("void ActivateTestDepthCallback" + CB, "after", HOLE_CB),
    ("void StaticEnvironment" + CB, "after", HOLE_CB.replace("if (do_colide && !(", "if (!(")), # it makes its joint whatever do_colide says
    ("void GetMaxDepthCallback" + CB, "after", HOLE_CB),
])

patch("xrGame/ActorCameraCollision.cpp", [
    ('#include "matrix_utils.h"\n', "after", '#include "portal_mod.h" // portal-mod E10\n'),
    ("    if (!do_collide)\n        return;\n    do_collide = false;\n", "after",
     "    // portal-mod E10: the camera box goes into a portal's hole with the body (else the eye stops short of the plane)\n"
     "    if (!(dGeomGetBody(c.geom.g1) && dGeomGetBody(c.geom.g2)) && portal_mod::hole(c.geom.pos, c.geom.normal))\n"
     "        return;\n"),
])

patch("xrGame/ActorCameras.cpp", [
    ('#include "phcollidevalidator.h"\n', "after", '#include "portal_mod.h" // portal-mod E10\n'),
    ("    CCameraBase* C = cam_Active();\n", "before",
     "    dangle.z += portal_mod::view_roll; // portal-mod E10: the view's roll after a portal, Lua brings it back to 0\n\n"),
])

patch("xrGame/level_script.cpp", [
    ('#include "map_location.h"\n', "after", '#include "portal_mod.h" // portal-mod E10\n'),
    ("static void portal_clear(int idx)\n", "before",
     "static void portal_view_roll(float roll) { portal_mod::view_roll = roll; } // portal-mod E10\n\n"),
    ('def("portal_set", &portal_set), def("portal_clear", &portal_clear),', "replace",
     'def("portal_set", &portal_set), def("portal_clear", &portal_clear), def("portal_view_roll", &portal_view_roll),'),
])

patch("xrGame/Actor.cpp", [
    ("    character_physics_support()->set_movement_position(m.c);\n    character_physics_support()->movement()->SetVelocity(0, 0, 0);\n}\n",
     "replace",
     "    character_physics_support()->set_movement_position(m.c);\n    character_physics_support()->movement()->SetVelocity(0, 0, 0);\n"
     "    fPrevCamPos = m.c.y; // portal-mod E10: no stair-step camera smoothing after a teleport (it dipped the view)\n}\n"),
])

patch("Layers/xrRenderPC_R4/r4_R_render.cpp", [
    ('            cmd_list.set_c("portal_params", portal.params.x, portal.params.y, portal.params.z, portal.params.w);\n\n'
     "            cmd_list.Render(6);\n",
     "replace",
     '            cmd_list.set_c("portal_params", portal.params.x, portal.params.y, portal.params.z, portal.params.w);\n\n'
     "            // portal-mod E10: the second quad behind the surface only when the camera is right at the portal (closer than\n"
     "            // the near plane can show it); otherwise it would peek over a fence or through the gaps between its boards\n"
     "            const float hw = portal.xform.i.magnitude(), hh = portal.xform.j.magnitude();\n"
     "            Fvector rel;\n"
     "            rel.sub(Device.vCameraPosition, portal.xform.c);\n"
     "            const bool close = -to_portal.dotproduct(portal.xform.k) < 0.6f && _abs(rel.dotproduct(portal.xform.i)) / hw < hw + 0.4f &&\n"
     "                _abs(rel.dotproduct(portal.xform.j)) / hh < hh + 0.4f;\n"
     "            cmd_list.Render(close ? 12 : 6);\n"),
])
