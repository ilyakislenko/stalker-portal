"""portal-mod engine patch E3: weapons without ammo in the HUD (the portal gun).

A weapon section with `portal_mod_brief = <text>` shows its own short name and icon in the HUD weapon panel and
<text> instead of "{AE}/{AC}" (like the knife, which has no ammo). The portal gun uses it: no gauss charges.
"""
from pathlib import Path

ENG = Path(r"E:\github\OGSR-Engine\ogsr_engine")
MARK = "portal-mod E3"


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


patch("xrGame/WeaponMagazined.cpp", [(
    "void CWeaponMagazined::GetBriefInfo(xr_string& str_name, xr_string& icon_sect_name, xr_string& str_count)\n{\n", "after",
    """    if (pSettings->line_exist(cNameSect(), "portal_mod_brief")) // portal-mod E3: a weapon without ammo (the portal gun)
    {
        str_name = NameShort();
        icon_sect_name = *cNameSect();
        str_count = pSettings->r_string(cNameSect(), "portal_mod_brief");
        return;
    }

""")])
