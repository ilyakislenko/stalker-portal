"""portal-mod engine patch E9: fixes for E8 (NPCs and corpses through portals).

- An NPC that came out of a portal hung in the air where it was put: when it is not walking a path, the AI takes the
  position from physics only while the physics character is enabled, and a standing NPC's character sleeps. It is
  enabled now (as CCustomMonster::ForceTransform does), so the NPC flies out and falls.
- A corpse on a floor portal did not fall in when the ragdoll's bounding-sphere centre was off the oval: now any part
  (element) of the body over the oval will do, and the rim/predictive tests are skipped for a body falling in.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E9"


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
    ("            mc->SetPosition(out);\n", "before",
     "            mc->EnableCharacter(); // portal-mod E9: a sleeping character would leave the NPC hanging in the air\n"),
    ("            if (A.n.y > 0.7f && vn < 2.f && d > -0.05f && d < R + 0.15f)\n"
     "            {\n"
     "                Fvector q;\n"
     "                q.sub(pos, A.c);\n"
     "                const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh;\n"
     "                if (x * x + y * y < 0.85f * 0.85f)\n"
     "                {\n",
     "replace",
     "            bool fell = false; // portal-mod E9: any part of the body over the oval will do (a ragdoll lies across it)\n"
     "            if (A.n.y > 0.7f && vn < 2.f && d > -0.05f && d < R + 0.15f)\n"
     "            {\n"
     "                for (CPhysicsElement* el : shell->Elements())\n"
     "                {\n"
     "                    Fmatrix m;\n"
     "                    el->GetGlobalTransformDynamic(&m);\n"
     "                    Fvector q;\n"
     "                    q.sub(m.c, A.c);\n"
     "                    const float x = q.dotproduct(A.r) / A.hw, y = q.dotproduct(A.u) / A.hh, h = q.dotproduct(A.n);\n"
     "                    if (h > -0.1f && h < 0.6f && x * x + y * y < 0.85f * 0.85f)\n"
     "                    {\n"
     "                        fell = true;\n"
     "                        break;\n"
     "                    }\n"
     "                }\n"
     "                if (fell)\n"
     "                {\n"),
    ("            if (d < -R || d - R > vn * fixed_step * 3.f + 0.05f)\n"
     "                continue; // behind it, or not there within the next steps\n",
     "replace",
     "            if (!fell && (d < -R || d - R > vn * fixed_step * 3.f + 0.05f))\n"
     "                continue; // behind it, or not there within the next steps\n"),
    ("            if (fx * fx + fy * fy > 1.f)\n                continue;\n", "replace",
     "            if (!fell && fx * fx + fy * fy > 1.f)\n                continue;\n"),
    ("            if (r > 0.8f)\n                shift.mul(", "replace",
     "            if (!fell && r > 0.8f)\n                shift.mul("),
])
