"""portal-mod engine patch E18: the player sees themselves through a portal.

In first person the actor's own model is hidden (CActor::UpdateCL: setVisible(!hud_view), "in HUD mode the actor's
model is not drawn"), so the see-through pass (E2) showed the room behind the player but not the player. For the portal
pass only the model is made visible - the body with the gun in its hands, as anyone else would see it - and hidden again
right after, so the main view stays first person.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E18"


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
    ("    Render->RenderPortalView(pos, dir, top, clip);\n", "replace",
     "    // portal-mod E18: the player through the portal - the first-person view hides the actor's model, the portal\n"
     "    // pass shows it (body and the gun in its hands) and hides it again for the main view\n"
     "    CActor* me = smart_cast<CActor*>(Level().CurrentViewEntity());\n"
     "    const bool show_me = me && !me->getVisible() && me->g_Alive() && !me->Holder();\n"
     "    if (show_me)\n"
     "        me->setVisible(TRUE);\n"
     "    Render->RenderPortalView(pos, dir, top, clip);\n"
     "    if (show_me)\n"
     "        me->setVisible(FALSE);\n"),
])
