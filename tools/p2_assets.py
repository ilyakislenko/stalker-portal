"""Convert the user's own Portal 2 files into STALKER (OGSR) formats, locally, into _gen/gamedata (never committed).

  python tools/p2_assets.py        (needs the universal-modder venv python for Pillow, and ffmpeg on E:)

Steps: universal-modder's Outer Wilds converter reads Portal 2's VPKs -> _p2/ (textures/*.png, sounds/*.wav),
then textures -> uncompressed A8R8G8B8 .dds and sounds -> mono Ogg Vorbis for the engine.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
P2 = ROOT / "_p2"
GEN = ROOT / "_gen" / "gamedata"
PORTAL2 = r"E:\SteamLibrary\steamapps\common\Portal 2"
CONVERTER = Path(r"E:\github\universal-modder\examples\outer-wilds-portal-gun\tools\convert.py")
FFMPEG = Path(r"E:\tools\um-local\universal-modder\ffmpeg\bin\ffmpeg.exe")

sys.path.insert(0, str(ROOT / "tools"))
from make_icons import write_dds_bgra  # noqa: E402

TEXTURES = {  # Portal 2 png -> textures\portal_mod\<name>.dds
    "portal_mask": "portal_mask",
    "noise-blur": "portal_noise",
    "portal-blue-color": "portal_ramp_blue",
    "portal-orange-color": "portal_ramp_orange",
    "portal_crosshairs": "portal_crosshairs",
    "v_portalgun": "v_portalgun",            # the gun's body; Portal 2 keeps a phong mask in alpha (constant 38)
    "v_portalgun_glass": "v_portalgun_glass",
    "v_portalgun_blue": "v_portalgun_blue",  # skins: lights blue / orange (alpha = self-illumination mask)
    "v_portalgun_orange": "v_portalgun_orange",
}
OPAQUE = {"v_portalgun"}  # alpha means something else in Portal 2; X-Ray model shaders read it as gloss


def main():
    if not (P2 / "manifest.json").exists():
        subprocess.run([sys.executable, "-I", str(CONVERTER), "--portal2", PORTAL2, "--out", str(P2)], check=True)
    tex_dir = GEN / "textures" / "portal_mod"
    for src, dst in TEXTURES.items():
        im = Image.open(P2 / "textures" / f"{src}.png").convert("RGBA")
        if im.size[1] < 4:  # 256x1 colour ramps: give the sampler some rows
            im = im.resize((im.size[0], 4), Image.NEAREST)
        if src in OPAQUE:
            im.putalpha(96)
        write_dds_bgra(im, tex_dir / f"{dst}.dds")
        print("texture", dst, im.size)
    snd_dir = GEN / "sounds" / "portal_mod"
    snd_dir.mkdir(parents=True, exist_ok=True)
    for wav in sorted((P2 / "sounds").glob("*.wav")):
        out = snd_dir / (wav.stem + ".ogg")
        subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "44100",
                        "-c:a", "libvorbis", "-q:a", "6", str(out)], check=True)
    # the gun's own "empty click" must be silent: pm_portals.script plays Portal 2's shot sounds
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1",
                    "-c:a", "libvorbis", str(snd_dir / "silence.ogg")], check=True)
    print("sounds", len(list(snd_dir.glob("*.ogg"))))
    (GEN.parent / "manifest.json").write_text(json.dumps({"from": PORTAL2, "textures": list(TEXTURES.values())}, indent=1))


if __name__ == "__main__":
    main()
