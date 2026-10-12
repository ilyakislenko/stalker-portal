"""Portal 2 portal gun viewmodel -> X-Ray (OGSR) skinned HUD model with embedded animations.

  python tools/p2_gun_ogf.py     (universal-modder venv python: numpy)
  in:  _p2/portalgun.owpg (tools/p2_assets.py; Unity axes = X-Ray axes: left-handed, X right, Y up, Z forward, metres)
  out: _gen/gamedata/meshes/portal_mod/wpn_portalgun_hud.ogf   (never committed: it is Valve's model)

Format (read from OGSR's loader): parent MT_SKELETON_ANIM with OGF_CHILDREN (one MT_SKELETON_GEOMDEF_ST per texture,
3-link vertices), OGF_S_BONE_NAMES, OGF_S_IKDATA (bind pose as setXYZi euler + position, local to parent),
OGF_S_SMPARAMS + OGF_S_MOTIONS (30 fps, rotation keys = conjugate quaternion * 32767, 16-bit translation keys).
"""
import math
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owpg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_p2" / "portalgun.owpg"
OUT = ROOT / "_gen" / "gamedata" / "meshes" / "portal_mod" / "wpn_portalgun_hud.ogf"

TEXTURES = {"v_portalgun": "portal_mod\\v_portalgun", "v_portalgun_glass": "portal_mod\\v_portalgun_glass"}
SHADER = "models\\model"

# X-Ray motion name <- Portal 2 sequence; StopAtEnd for one-shot motions (else the HUD state never ends)
MOTIONS = [  # (name, sequence, one_shot)
    ("idle", "idle", False),
    ("draw", "draw", True),
    ("holster", "holster", True),
    ("shoot", "fire1", True),
    ("reload", "fizzle", True),
    ("idle_sprint", "lowidle", False),
    ("idle_moving", "idle", False),
    ("dryfire", "dryfire", True),
]
ESM_STOP_AT_END = 2

# chunk ids (xr_3da/fmesh.h)
OGF_HEADER, OGF_TEXTURE, OGF_VERTICES, OGF_INDICES, OGF_CHILDREN = 1, 2, 3, 4, 9
OGF_S_BONE_NAMES, OGF_S_MOTIONS, OGF_S_SMPARAMS, OGF_S_IKDATA, OGF_S_DESC = 13, 14, 15, 16, 18
MT_SKELETON_ANIM, MT_SKELETON_GEOMDEF_ST = 3, 5
VF_3W = 0x481C6600


def chunk(cid, data):
    return struct.pack("<II", cid, len(data)) + data


def sz(text):
    return text.encode("cp1251") + b"\0"


def header(model_type, pts):
    lo, hi = pts.min(0), pts.max(0)
    c = (lo + hi) / 2
    r = float(np.linalg.norm(pts - c, axis=1).max())
    return struct.pack("<BBH10f", 4, model_type, 0, *lo, *hi, *c, r)


# ---------------------------------------------------------------- math (column-vector matrices, Hamilton quaternions)
def q2m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def m2q(m):
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = ((m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s)
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = (0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s)
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = ((m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s)
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = ((m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s)
    q = np.array(q)
    return q / np.linalg.norm(q)


def trs(p, q):
    m = np.eye(4)
    m[:3, :3] = q2m(q)
    m[:3, 3] = p
    return m


def xray_rows(m):
    """Column-vector 4x4 -> X-Ray row-vector rotation rows i, j, k (local axes in parent space)."""
    r = m[:3, :3].T
    return r[0], r[1], r[2]


def set_hpb(h, p, b):
    """X-Ray Fmatrix::setHPB rows (xrCore/_matrix.h)."""
    ch, sh, cp, sp, cb, sb = math.cos(h), math.sin(h), math.cos(p), math.sin(p), math.cos(b), math.sin(b)
    i = (ch * cb - sp * sh * sb, -cp * sb, sp * ch * sb + sh * cb)
    j = (sp * sh * cb + ch * sb, cp * cb, sh * sb - sp * ch * cb)
    k = (-cp * sh, sp, cp * ch)
    return np.array([i, j, k])


def bind_euler(local):
    """The XYZi euler X-Ray's bone bind uses (bind = setXYZi(rot) = setHPB(-rot.y, -rot.x, -rot.z))."""
    i, j, k = xray_rows(local)
    p = math.asin(max(-1.0, min(1.0, k[1])))
    h = math.atan2(-k[0], k[2])
    b = math.atan2(-i[1], j[1])
    err = np.abs(set_hpb(h, p, b) - np.array([i, j, k])).max()
    assert err < 1e-4, f"euler round trip error {err}"
    return (-p, -h, -b)


# ---------------------------------------------------------------- build
def main():
    m = owpg.load(SRC)
    nb = len(m.bones)
    names = [b.name.lower() for b in m.bones]
    parents = [b.parent for b in m.bones]
    roots = [i for i, p in enumerate(parents) if p < 0]
    main_root = roots[0]
    for r in roots[1:]:  # X-Ray wants exactly one root: hang the others on the first
        parents[r] = main_root

    # bind pose: global = inverse(pose_to_bone), so skinning matches the vertex data exactly
    g_bind = [np.linalg.inv(b.pose_to_bone) for b in m.bones]
    l_bind = [g_bind[i] if parents[i] < 0 else np.linalg.inv(g_bind[parents[i]]) @ g_bind[i] for i in range(nb)]

    # ---- skeleton chunks
    bn = struct.pack("<I", nb)
    ik = b""
    for i in range(nb):
        bn += sz(names[i]) + sz("" if parents[i] < 0 else names[parents[i]])
        bn += struct.pack("<9f3f3f", 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0.05, 0.05, 0.05)  # bone-local OBB
        rot = bind_euler(l_bind[i])
        pos = l_bind[i][:3, 3]
        ik += struct.pack("<I", 1) + sz("default_object")  # "" is not "none": shared_str("") is non-null, the engine looks it up
        ik += struct.pack("<HH", 0, 0) + b"\0" * 60 + b"\0" * 16 + b"\0" * 32         # SBoneShape: none
        ik += struct.pack("<I", 0) + struct.pack("<12f", *([0, 0, 1, 1] * 3))          # SJointIKData: rigid
        ik += struct.pack("<2fI3f", 1, 1, 0, 0, 0, 0)
        ik += struct.pack("<3f3f", *rot, *pos)
        ik += struct.pack("<f3f", 1.0, 0, 0, 0)

    # ---- children: one per texture, 3-link vertices
    children = b""
    all_pos = []
    for ci, (tex, tris) in enumerate(m.submeshes):
        used = np.unique(tris.reshape(-1))
        remap = -np.ones(len(m.pos), dtype=np.int64)
        remap[used] = np.arange(len(used))
        t = remap[tris]
        P, N, UV = m.pos[used], m.nrm[used], m.uv[used]
        # tangents from UVs (no bump map is used, but the vertex wants them)
        T = np.zeros_like(P)
        for a, b_, c in t:
            e1, e2 = P[b_] - P[a], P[c] - P[a]
            d1, d2 = UV[b_] - UV[a], UV[c] - UV[a]
            r = d1[0] * d2[1] - d2[0] * d1[1]
            tan = (e1 * d2[1] - e2 * d1[1]) / (r if abs(r) > 1e-12 else 1e-12)
            T[a] += tan
            T[b_] += tan
            T[c] += tan
        T = T - N * np.einsum("ij,ij->i", T, N)[:, None]
        bad = np.linalg.norm(T, axis=1) < 1e-8
        T[bad] = np.cross(N[bad], [0, 1, 0]) + 1e-6
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        B = np.cross(N, T)
        # influences: strongest first, padded to three
        vb, vw = m.vbones[used], m.vweights[used]
        order = np.argsort(-vw, axis=1)
        vb = np.take_along_axis(vb, order, 1)[:, :3]
        vw = np.take_along_axis(vw, order, 1)[:, :3]
        vw = vw / np.maximum(vw.sum(1, keepdims=True), 1e-6)
        vb[vw <= 0] = vb[:, :1].repeat(3, 1)[vw <= 0]
        verts = bytearray(struct.pack("<II", VF_3W, len(used)))
        for v in range(len(used)):
            verts += struct.pack("<3H12f2f2f", *[int(x) for x in vb[v]], *P[v], *N[v], *T[v], *B[v], vw[v][0], vw[v][1], UV[v][0], UV[v][1])
        idx = struct.pack("<I", t.size) + struct.pack(f"<{t.size}H", *t.reshape(-1).tolist())
        child = chunk(OGF_HEADER, header(MT_SKELETON_GEOMDEF_ST, P))
        child += chunk(OGF_TEXTURE, sz(TEXTURES.get(tex, "portal_mod\\" + tex)) + sz(SHADER))
        child += chunk(OGF_VERTICES, bytes(verts)) + chunk(OGF_INDICES, idx)
        children += chunk(ci, child)
        all_pos.append(P)

    # ---- motions
    seqs = {s.name: s for s in m.sequences}
    smp = struct.pack("<HH", 3, 1) + sz("default") + struct.pack("<H", nb)
    for i in range(nb):
        smp += sz(names[i]) + struct.pack("<I", i)
    smp += struct.pack("<H", len(MOTIONS))
    mot = chunk(0, struct.pack("<I", len(MOTIONS)))
    for mi, (name, seq_name, one_shot) in enumerate(MOTIONS):
        smp += sz(name) + struct.pack("<IHH4f", ESM_STOP_AT_END if one_shot else 0, 0, mi, 1.0, 1.0, 2.0, 2.0)
        s = seqs[seq_name]
        fr = s.frames  # [f][bone][p q]
        nf = len(fr)
        body = sz(name) + struct.pack("<I", nf)
        for bi in range(nb):
            locs = []
            for f in range(nf):
                L = trs(fr[f, bi, :3], fr[f, bi, 3:])
                if parents[bi] != m.bones[bi].parent:  # re-hung root: express it under the new parent at that frame
                    pg = trs(fr[f, parents[bi], :3], fr[f, parents[bi], 3:])
                    L = np.linalg.inv(pg) @ L
                locs.append(L)
            qs = np.array([m2q(L[:3, :3]) for L in locs])
            for f in range(1, nf):  # keep neighbouring keys on the same hemisphere
                if np.dot(qs[f], qs[f - 1]) < 0:
                    qs[f] = -qs[f]
            ts = np.array([L[:3, 3] for L in locs])
            stored = np.round(np.column_stack([-qs[:, 0], -qs[:, 1], -qs[:, 2], qs[:, 3]]) * 32767).astype(np.int16)
            lo, hi = ts.min(0), ts.max(0)
            moving = (hi - lo).max() > 1e-5
            flags = (1 | 4) if moving else 0
            body += struct.pack("<B", flags)
            body += struct.pack("<I", 0) + stored.tobytes()
            if moving:
                init = (lo + hi) / 2
                size = np.where(hi - lo > 1e-9, (hi - lo) / 65534, 0.0)
                keys = np.round(np.where(size > 0, (ts - init) / np.where(size > 0, size, 1), 0)).astype(np.int16)
                body += struct.pack("<I", 0) + keys.tobytes() + struct.pack("<3f3f", *size, *init)
            else:
                body += struct.pack("<3f", *ts[0])
        mot += chunk(mi + 1, body)

    pts = np.concatenate(all_pos)
    ogf = chunk(OGF_HEADER, header(MT_SKELETON_ANIM, pts))
    ogf += chunk(OGF_CHILDREN, children)
    ogf += chunk(OGF_S_BONE_NAMES, bn)
    ogf += chunk(OGF_S_IKDATA, ik)
    ogf += chunk(OGF_S_SMPARAMS, smp)
    ogf += chunk(OGF_S_MOTIONS, mot)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(ogf)
    print(f"wrote {OUT} ({len(ogf) / 1024:.0f} KB): {nb} bones, {len(m.submeshes)} meshes, {len(MOTIONS)} motions")


if __name__ == "__main__":
    main()
