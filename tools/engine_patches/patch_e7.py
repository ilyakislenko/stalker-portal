"""portal-mod engine patch E7: Portal 2 style funnelling for physics bodies.

A body that would meet the portal plane up to FUNNEL metres outside the oval is pulled in: it is teleported as if it
had crossed at the nearest point well inside the oval (radius 0.8). Thrown grenades leave the hand bone, not the
camera, so a throw aimed at the middle of a portal can otherwise clip its rim and bounce off the wall.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E7"


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


patch("xrGame/Level.cpp", [
    ("static void portal_mod_teleport_shell(CPhysicsShell* shell, const portal_mod::Frame& A, const portal_mod::Frame& B, float push)\n",
     "replace",
     "static void portal_mod_teleport_shell(CPhysicsShell* shell, const portal_mod::Frame& A, const portal_mod::Frame& B, float push,\n"
     "                                      const Fvector& shift) // portal-mod E7: funnelling moves the entry point by `shift`\n"),
    ("    form.c.mad(B.n, push);\n", "after", "    form.c.add(map_dir(A, B, shift));\n"),
    ("            Fvector q;\n"
     "            q.mad(pos, v, _max(d, 0.f) / vn).sub(A.c); // where it meets the portal plane\n"
     "            const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;\n"
     "            if (x * x + y * y > 1.f)\n"
     "                continue;\n"
     "\n"
     "            portal_mod_teleport_shell(shell, A, B, _max(d, 0.f) + R + 0.05f);\n",
     "replace",
     "            Fvector q;\n"
     "            q.mad(pos, v, _max(d, 0.f) / vn).sub(A.c); // where it meets the portal plane\n"
     "            // portal-mod E7: up to FUNNEL metres outside the oval it is pulled in (Portal 2 funnelling)\n"
     "            constexpr float FUNNEL = 0.35f;\n"
     "            const float qx = q.dotproduct(A.r), qy = q.dotproduct(A.u);\n"
     "            const float fx = qx / (A.hw + FUNNEL), fy = qy / (A.hh + FUNNEL);\n"
     "            if (fx * fx + fy * fy > 1.f)\n"
     "                continue;\n"
     "            const float x = qx / A.hw, y = qy / A.hh, r = _sqrt(x * x + y * y);\n"
     "            Fvector shift{};\n"
     "            if (r > 0.8f)\n"
     "                shift.mul(A.r, (x * 0.8f / r - x) * A.hw).mad(A.u, (y * 0.8f / r - y) * A.hh);\n"
     "\n"
     "            portal_mod_teleport_shell(shell, A, B, _max(d, 0.f) + R + 0.05f, shift);\n"),
    ('            Msg("[portal_mod] %s went through portal %d at %.1f m/s", holder->cName().c_str(), i, v.magnitude());\n',
     "replace",
     '            Msg("[portal_mod] %s went through portal %d at %.1f m/s%s", holder->cName().c_str(), i, v.magnitude(),\n'
     '                r > 1.f ? " (funnelled)" : "");\n'),
])
