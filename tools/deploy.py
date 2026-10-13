"""Install / uninstall the mod into the user's S.T.A.L.K.E.R. SoC (OGSR) gamedata.

  python -I tools/deploy.py                 install (first run backs up the files it patches + saves)
  python -I tools/deploy.py --autotest X    install with [portal_mod] autotest = X (a lab scenario), autotest_quit = true
  python -I tools/deploy.py --uninstall     remove our files and hook lines

What it touches in the game:
  gamedata/config/portal_mod/*, gamedata/scripts/portal_mod.script, pm_*.script, mod_manager.script,
  gamedata/config/ui/ui_mod_manager.xml, gamedata/textures/ui/ui_icon_equipment_77.dds
  gamedata/config/external.ltx          + one #include line
  gamedata/scripts/bind_stalker.script  + hook lines (marked PORTAL_MOD HOOK): actor reinit/destroy/update, and the
                                          "AI Bot" switch of My Mods inside the user's bot hook
  gamedata/scripts/ui_main_menu.script  + the "My Mods" button callback (marked)
  gamedata/config/ui/ui_mm_main.xml     + a "My Mods" button before every Options button (marked)
  Bytes of these files are otherwise untouched; --uninstall removes the marked lines.
Text files (.ltx .xml .script) are UTF-8 in the repo and written as cp1251, the game's encoding.
"""
import argparse
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mod" / "gamedata"
GEN = ROOT / "_gen" / "gamedata"  # converted from the user's Portal 2 by tools/p2_assets.py (never committed)
GAME = Path(r"E:\Games\S.T.A.L.K.E.R. Shadow of Chernobyl")
GD = GAME / "gamedata"
SAVES = Path(r"C:\Users\User\docume~1\stalke~3\savedgames")
BACKUP = ROOT / "_backup"
MARK = b"-- PORTAL_MOD HOOK"
XML_MARK = b"<!-- PORTAL_MOD HOOK -->"
INCLUDE = b'#include "portal_mod\\portal_mod.ltx" ; PORTAL_MOD'
TEXT = {".ltx", ".xml", ".script"}

HOOKS = {  # file -> [(anchor, where, line, at every occurrence)]
    "scripts/bind_stalker.script": [
        (b"\tself.object:set_callback(callback.take_item_from_box, self.take_item_from_box, self)\r\n", "after",
         b"\tif portal_mod then portal_mod.on_actor_reinit(self) end " + MARK + b"\r\n", False),
        (b"\tobject_binder.net_destroy(self)\r\n", "before",
         b"\tif portal_mod then portal_mod.on_actor_destroy(self.object) end " + MARK + b"\r\n", False),
        (b"\t\tbot_core.on_game_update()\r\n\tend)\r\n", "after",
         b"\tif portal_mod then portal_mod.on_update(delta) end " + MARK + b"\r\n", False),
        (b"\t\tif not bot_core then return end\r\n", "after",
         b'\t\tif mod_manager and not mod_manager.enabled("ai_bot") then return end ' + MARK + b"\r\n", False),
    ],
    "scripts/ui_main_menu.script": [
        (b'\tself:AddCallback("btn_options", ui_events.BUTTON_CLICKED, self.OnButton_options_clicked, self)\r\n', "after",
         b'\tself:AddCallback("btn_mods", ui_events.BUTTON_CLICKED, function() if mod_manager then mod_manager.open(self) end end, self) '
         + MARK + b"\r\n", False),
    ],
    "config/ui/ui_mm_main.xml": [
        (b'\t\t<btn name="btn_options"\t\tcaption="ui_mm_options_n" />\r\n', "before",
         b'\t\t<btn name="btn_mods"\t\tcaption="My Mods" /> ' + XML_MARK + b"\r\n", True),
    ],
}


def backup_once():
    """Each game file we patch is saved before our first touch; the saves once, on the very first install."""
    orig = BACKUP / "original"
    first = not orig.exists()
    for rel in ["config/external.ltx"] + list(HOOKS):
        dst = orig / rel
        if not dst.exists() and (GD / rel).exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GD / rel, dst)
            print(f"backup: {rel}")
    if first and SAVES.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copytree(SAVES, BACKUP / f"savedgames-{stamp}")
        print(f"backup: savedgames-{stamp}")


def our_files():
    """(source, path relative to gamedata) for the mod's own files and the locally converted Portal 2 assets."""
    out = []
    for root in (SRC, GEN):
        if root.exists():
            out += [(p, p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    return out


def copy_files(autotest):
    for p, rel in our_files():
        dst = GD / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() in TEXT:
            text = p.read_text(encoding="utf-8")
            if autotest and p.name == "portal_mod.ltx":
                text = re.sub(r"(?m)^(autotest\s*=\s*)none", lambda m: m.group(1) + autotest, text)
                text = re.sub(r"(?m)^(autotest_quit\s*=\s*)false", r"\1true", text)
            dst.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("cp1251"))
        else:
            shutil.copy2(p, dst)
        print(f"  {rel}")


def patch_hooks():
    """Our marked lines into the game's files; each line once (a re-run adds nothing)."""
    for rel, hooks in HOOKS.items():
        path = GD / rel
        if not path.exists():
            print(f"{rel}: not in the game, skipped")
            continue
        b = path.read_bytes()
        added = 0
        for anchor, where, line, every in hooks:
            if line in b:
                continue
            n = b.count(anchor)
            if n == 0 or (n != 1 and not every):
                print(f"! {rel}: anchor found {n} times, hook skipped: {anchor!r}")
                continue
            out, pos = [], 0
            while True:
                i = b.find(anchor, pos)
                if i < 0:
                    break
                at = i + len(anchor) if where == "after" else i
                out.append(b[pos:at] + line)
                pos = at + (len(anchor) if where == "before" else 0)
                if where == "before":
                    out[-1] += anchor
                added += 1
                if not every:
                    break
            b = b"".join(out) + b[pos:]
        path.write_bytes(b)
        print(f"{rel}: {added} hook line(s) added")


def patch_external():
    path = GD / "config" / "external.ltx"
    b = path.read_bytes()
    if INCLUDE in b:
        return
    if not b.endswith(b"\n"):
        b += b"\r\n"
    path.write_bytes(b + INCLUDE + b"\r\n")
    print("external.ltx: include added")


def uninstall():
    for _, rel in our_files():
        dst = GD / rel
        if dst.exists():
            dst.unlink()
    d = GD / "config" / "portal_mod"
    if d.exists() and not any(d.iterdir()):
        d.rmdir()
    for rel in HOOKS:
        path = GD / rel
        if path.exists():
            b = path.read_bytes()
            b = b"".join(l for l in b.splitlines(keepends=True) if MARK not in l and XML_MARK not in l)
            path.write_bytes(b)
    path = GD / "config" / "external.ltx"
    b = path.read_bytes()
    b = b"".join(l for l in b.splitlines(keepends=True) if INCLUDE not in l)
    path.write_bytes(b)
    print("uninstalled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autotest", metavar="SCENARIO", help="a lab scenario: boots, portals, gun, bar, npc, walk, mods...")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    if a.uninstall:
        uninstall()
        return
    backup_once()
    copy_files(a.autotest)
    patch_external()
    patch_hooks()


if __name__ == "__main__":
    main()
