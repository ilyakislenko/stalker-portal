"""Reader for portalgun.owpg (universal-modder's Outer Wilds converter output: Portal 2 v_portalgun in Unity space,
left-handed, X right, Y up, Z forward, metres - the same axes as X-Ray).

  python tools/owpg.py _p2/portalgun.owpg      (prints a summary)
"""
import struct
import sys
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Bone:
    name: str
    parent: int
    pos: np.ndarray        # local to parent (bind)
    quat: np.ndarray       # x y z w, local to parent (bind)
    pose_to_bone: np.ndarray  # 4x4


@dataclass
class Sequence:
    name: str
    activity: str
    looping: bool
    fps: float
    frames: np.ndarray     # [frame][bone][px py pz qx qy qz qw], local to parent


@dataclass
class Model:
    bones: list = field(default_factory=list)
    pos: np.ndarray = None
    nrm: np.ndarray = None
    uv: np.ndarray = None
    vbones: np.ndarray = None   # [v][4] int
    vweights: np.ndarray = None  # [v][4] float
    submeshes: list = field(default_factory=list)  # (texture, tris[n][3])
    attachments: list = field(default_factory=list)  # (name, bone, pos, quat)
    sequences: list = field(default_factory=list)


class _R:
    def __init__(self, b):
        self.b, self.p = b, 0

    def i(self, n=1):
        v = struct.unpack_from(f"<{n}i", self.b, self.p)
        self.p += 4 * n
        return v if n > 1 else v[0]

    def f(self, n=1):
        v = struct.unpack_from(f"<{n}f", self.b, self.p)
        self.p += 4 * n
        return v if n > 1 else v[0]

    def s(self):
        n = self.i()
        t = self.b[self.p:self.p + n].decode("utf-8")
        self.p += n
        return t

    def arr(self, dtype, count, shape):
        a = np.frombuffer(self.b, dtype=dtype, count=count, offset=self.p).reshape(shape)
        self.p += a.nbytes
        return a.copy()


def load(path):
    r = _R(open(path, "rb").read())
    assert r.b[:4] == b"OWPG"
    r.p = 4
    assert r.i() == 1
    m = Model()
    for _ in range(r.i()):
        name, parent = r.s(), r.i()
        pos, quat = np.array(r.f(3)), np.array(r.f(4))
        ptb = np.array(r.f(16)).reshape(4, 4)
        m.bones.append(Bone(name, parent, pos, quat, ptb))
    n = r.i()
    m.pos = r.arr("<f4", n * 3, (n, 3))
    m.nrm = r.arr("<f4", n * 3, (n, 3))
    m.uv = r.arr("<f4", n * 2, (n, 2))
    m.vbones = r.arr("<i4", n * 4, (n, 4))
    m.vweights = r.arr("<f4", n * 4, (n, 4))
    for _ in range(r.i()):
        tex, cnt = r.s(), r.i()
        m.submeshes.append((tex, r.arr("<i4", cnt, (cnt // 3, 3))))
    for _ in range(r.i()):
        name, bone = r.s(), r.i()
        m.attachments.append((name, bone, np.array(r.f(3)), np.array(r.f(4))))
    nb = len(m.bones)
    for _ in range(r.i()):
        name, act, loop, fps, nf = r.s(), r.s(), r.i(), r.f(), r.i()
        m.sequences.append(Sequence(name, act, bool(loop), fps, r.arr("<f4", nf * nb * 7, (nf, nb, 7))))
    return m


if __name__ == "__main__":
    m = load(sys.argv[1])
    print(len(m.bones), "bones:", ", ".join(f"{i}:{b.name}<-{b.parent}" for i, b in enumerate(m.bones)))
    print(len(m.pos), "verts, bbox", m.pos.min(0).round(3), m.pos.max(0).round(3), "max bones/vert", int((m.vweights > 0).sum(1).max()))
    for tex, t in m.submeshes:
        print("submesh", tex, len(t), "tris")
    print("attachments:", ", ".join(a[0] for a in m.attachments))
    for s in m.sequences:
        print(f"seq {s.name:16} act={s.activity:24} loop={s.looping} fps={s.fps} frames={len(s.frames)}")
