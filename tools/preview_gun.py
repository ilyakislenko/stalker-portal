"""Software preview of the converted portal gun: skin the bind-pose mesh with a sequence frame and draw it from the
eye (origin, +Z forward, +Y up), the way the HUD should show it. Compares the owpg data with what the game shows.

  python tools/preview_gun.py [sequence] [frame] [fov] [out.png]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owpg  # noqa: E402
from p2_gun_ogf import trs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def pose_globals(m, frame):
    G = [None] * len(m.bones)
    for i, b in enumerate(m.bones):
        L = trs(frame[i, :3], frame[i, 3:])
        G[i] = L if b.parent < 0 else G[b.parent] @ L
    return G


def main():
    seq = sys.argv[1] if len(sys.argv) > 1 else "idle"
    fi = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    fov = float(sys.argv[3]) if len(sys.argv) > 3 else 54.0
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / "_vanilla" / "gun_preview.png"
    m = owpg.load(ROOT / "_p2" / "portalgun.owpg")
    s = next(x for x in m.sequences if x.name == seq)
    G = pose_globals(m, s.frames[fi])
    skin = [G[i] @ m.bones[i].pose_to_bone for i in range(len(m.bones))]
    P = np.c_[m.pos, np.ones(len(m.pos))]
    world = np.zeros((len(P), 3))
    for k in range(4):
        w = m.vweights[:, k]
        for bi in np.unique(m.vbones[:, k]):
            sel = (m.vbones[:, k] == bi) & (w > 0)
            world[sel] += (P[sel] @ skin[bi].T)[:, :3] * w[sel, None]
    print("posed bbox", world.min(0).round(3), world.max(0).round(3))
    W, H = 960, 540
    f = (H / 2) / np.tan(np.radians(fov) / 2)
    img = Image.new("RGB", (W, H), (60, 70, 60))
    d = ImageDraw.Draw(img)
    tris = np.concatenate([t for _, t in m.submeshes])
    depth = world[tris].mean(1)[:, 2]
    for t in tris[np.argsort(-depth)]:
        v = world[t]
        if (v[:, 2] < 0.01).any():
            continue
        xy = [(W / 2 + f * x / z, H / 2 - f * y / z) for x, y, z in v]
        n = np.cross(v[1] - v[0], v[2] - v[0])
        shade = int(120 + 120 * abs(n[1] / (np.linalg.norm(n) + 1e-9)))
        d.polygon(xy, fill=(shade, shade, shade))
    img.save(out)
    print("preview", out)


if __name__ == "__main__":
    main()
