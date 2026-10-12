"""Install / uninstall the mod into the user's S.T.A.L.K.E.R. SoC (OGSR) gamedata.

  python -I tools/deploy.py                 install (first run backs up the files it patches + saves)
  python -I tools/deploy.py --autotest X    install with [portal_mod] autotest = X (boots|gallery|portals), autotest_quit = true
  python -I tools/deploy.py --uninstall     remove our files and hook lines

What it touches in the game:
  gamedata/config/portal_mod/*, gamedata/scripts/portal_mod.script, pm_*.script, gamedata/textures/ui/ui_icon_equipment_77.dds
  gamedata/config/external.ltx       + one #include line
  gamedata/scripts/bind_stalker.script + three hook lines (marked PORTAL_MOD HOOK), bytes otherwise untouched
Text files (.ltx .xml .script) are UTF-8 in the repo and written as cp1251, the game's encoding.
"""
import argparse
import re
import shutil
import sys
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
INCLUDE = b'#include "portal_mod\\portal_mod.ltx" ; PORTAL_MOD'
TEXT = {".ltx", ".xml", ".script"}

HOOKS = [  # (anchor, where, line)
    (b"\tself.object:set_callback(callback.take_item_from_box, self.take_item_from_box, self)\r\n", "after",
     b"\tif portal_mod then portal_mod.on_actor_reinit(self) end " + MARK + b"\r\n"),
    (b"\tobject_binder.net_destroy(self)\r\n", "before",
     b"\tif portal_mod then portal_mod.on_actor_destroy(self.object) end " + MARK + b"\r\n"),
    (b"\t\tbot_core.on_game_update()\r\n\tend)\r\n", "after",
     b"\tif portal_mod then portal_mod.on_update(delta) end " + MARK + b"\r\n"),
]


def backup_once():
    orig = BACKUP / "original"
    if orig.exists():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for rel in ["config/external.ltx", "scripts/bind_stalker.script"]:
        dst = orig / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GD / rel, dst)
    if SAVES.exists():
        shutil.copytree(SAVES, BACKUP / f"savedgames-{stamp}")
    print(f"backup: {orig} and savedgames-{stamp}")


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


def patch_bind_stalker():
    path = GD / "scripts" / "bind_stalker.script"
    b = path.read_bytes()
    if MARK in b:
        print("bind_stalker.script: hooks already present")
        return
    for anchor, where, line in HOOKS:
        if b.count(anchor) != 1:
            sys.exit(f"bind_stalker.script: anchor found {b.count(anchor)} times, expected 1: {anchor!r}")
        i = b.index(anchor)
        at = i + len(anchor) if where == "after" else i
        b = b[:at] + line + b[at:]
    path.write_bytes(b)
    print("bind_stalker.script: 3 hook lines added")


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
    path = GD / "scripts" / "bind_stalker.script"
    b = path.read_bytes()
    b = b"".join(l for l in b.splitlines(keepends=True) if MARK not in l)
    path.write_bytes(b)
    path = GD / "config" / "external.ltx"
    b = path.read_bytes()
    b = b"".join(l for l in b.splitlines(keepends=True) if INCLUDE not in l)
    path.write_bytes(b)
    print("uninstalled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autotest", metavar="SCENARIO", help="boots | gallery | portals")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    if a.uninstall:
        uninstall()
        return
    backup_once()
    copy_files(a.autotest)
    patch_external()
    patch_bind_stalker()


if __name__ == "__main__":
    main()
