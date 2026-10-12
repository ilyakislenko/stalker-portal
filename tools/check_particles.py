"""Check that every particle name quoted in the mod's scripts exists in the game's particles.xr.

An unknown name passed to particles_object() is a FATAL error ("group") in OGSR, so run this before deploying.
  python -I tools/check_particles.py            (builds _vanilla/particle_names.txt on first run)
"""
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XR = ROOT / "_vanilla" / "particles.xr"
NAMES = ROOT / "_vanilla" / "particle_names.txt"
GAME = r"E:\Games\S.T.A.L.K.E.R. Shadow of Chernobyl"


def chunks(data):
    p = 0
    while p + 8 <= len(data):
        cid, sz = struct.unpack_from("<II", data, p)
        yield cid, data[p + 8:p + 8 + sz]
        p += 8 + sz


def build():
    if not XR.exists():
        subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "xrdb_unpack.py"), GAME, str(ROOT / "_vanilla"), "--only", "particles.xr"], check=True)
    names = {}
    for cid, d in chunks(XR.read_bytes()):
        kind = {3: "effect", 4: "group"}.get(cid & 0x7FFFFFFF)  # PS_CHUNK_SECONDGEN / THIRDGEN
        if not kind:
            continue
        for _, od in chunks(d):
            for sid, sd in chunks(od):
                if sid == 2:  # name chunk
                    names[sd.split(b"\0")[0].decode("cp1251")] = kind
                    break
    NAMES.write_text("\n".join(f"{v}\t{k}" for k, v in sorted(names.items())), encoding="utf-8")
    return names


def main():
    names = build() if not NAMES.exists() else dict(reversed(l.split("\t")) for l in NAMES.read_text(encoding="utf-8").splitlines())
    bad = 0
    for script in (ROOT / "mod" / "gamedata" / "scripts").glob("*.script"):
        for lit in re.findall(r'"([^"\s]+\\\\[^"\s]+)"', script.read_text(encoding="utf-8")):
            name = lit.replace("\\\\", "\\")
            if name.split("\\")[0] in ("ui", "weapons", "detectors", "characters_voice", "device", "material"):
                continue  # textures and sounds
            if name.startswith(("anomaly", "ghoul", "static", "explosions", "glow", "hit_fx", "monsters", "industrial")):
                status = names.get(name, "MISSING")
                if status == "MISSING":
                    bad += 1
                print(f"{status:8} {script.name}: {name}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
