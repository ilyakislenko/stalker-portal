"""portal-mod engine patch E5: log how many bullets went through portals (once per frame, from the main thread).

The bullet worker thread counts portal crossings in an atomic; CBulletManager::CommitRenderSet prints and resets it:
    [portal_mod] 3 bullet(s) went through a portal
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E5"


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
        at = i + len(anchor) if how == "after" else i
        s = s[:at] + text + s[at:]
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + s.encode("utf-8"))
    print("patched", rel)


patch("xrGame/Level_Bullet_Manager.cpp", [
    ("void CBulletManager::UpdateWorkload()\n", "before",
     "#include <atomic>\n"
     "static std::atomic<u32> portal_mod_bullets{0}; // portal-mod E5: crossings since the last frame\n\n"),
    ("        bullet->portal_dist = 0.f;\n", "after",
     "        portal_mod_bullets.fetch_add(1, std::memory_order_relaxed); // portal-mod E5\n"),
    ("    m_portals_linked = portal_mod::linked() && portal_mod::get_frame(0, m_pf[0]) && portal_mod::get_frame(1, m_pf[1]);\n",
     "after",
     "    if (const u32 n = portal_mod_bullets.exchange(0)) // portal-mod E5\n"
     "        Msg(\"[portal_mod] %u bullet(s) went through a portal\", n);\n"),
])
