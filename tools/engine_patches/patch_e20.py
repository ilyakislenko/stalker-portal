"""portal-mod engine patch E20: out of a portal at speed the ground slows the player as in Portal 2, not to a dead stop.

Logged per physics step (user: "sometimes the energy is kept, sometimes 0"): out of a wall portal standing on the ground
the player flew at 19.4 m/s (E17), touched the ground within 0.2 s and lost 40 % of the speed in that one step, then
~8 % a step (about 80 m/s^2), under a run E17 gave the control back and with no key held it stopped dead. The
character's contacts take the ground material's full friction whenever no movement key is held
(CPHSimpleCharacter::InitContact: `is_control` contacts are frictionless, the others get mu * m_friction_factor) - so
with a key held the player slid on, without one stopped: the "sometimes".
While flying out of a portal (E17's m_portal_fly) the contacts are frictionless and the ground slows the player by
Source's own rule (Portal 2: sv_friction 4, sv_stopspeed 100 units = 1.9 m/s): each step the horizontal speed drops by
max(speed, 1.9) * 4 * dt - from 19 m/s about a second and 4-5 m of sliding.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E20"


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
    ("                const dReal k = 1.f - 3.f * fixed_step;\n"
     "                dBodySetLinearVel(m_body, velocity[0] * k, velocity[1], velocity[2] * k);\n", "replace",
     "                // portal-mod E20: Source's ground friction (Portal 2: sv_friction 4, sv_stopspeed 100 units = 1.9 m/s)\n"
     "                const dReal sp = _sqrt(velocity[0] * velocity[0] + velocity[2] * velocity[2]);\n"
     "                if (sp > EPS_L)\n"
     "                {\n"
     "                    const dReal k = _max(sp - _max(sp, 1.9f) * 4.f * fixed_step, 0.f) / sp;\n"
     "                    dBodySetLinearVel(m_body, velocity[0] * k, velocity[1], velocity[2] * k);\n"
     "                }\n"),
    ("        c->surface.mu *= (1.f + b_clamb_jump * 3.f) * m_friction_factor;\n    }\n", "replace",
     "        c->surface.mu *= (1.f + b_clamb_jump * 3.f) * m_friction_factor;\n"
     "        if (m_portal_fly)\n"
     "            c->surface.mu = 0.f; // portal-mod E20: flying out of a portal, the ground's friction is Source's (PhDataUpdate)\n"
     "    }\n"),
])
