"""Portal 2 portal gun world model (models/weapons/w_portalgun) -> X-Ray (OGSR) world visual: the gun in the player's
hands seen from outside (through a portal: engine E18), on the ground and on an NPC. Until now the world model was the
Gauss rifle's (wpn_portalgun inherits wpn_gauss).
  python tools/p2_world.py [--info]      (numpy, Pillow)
  in:  Portal 2's VPKs, read with universal-modder's Source readers (vpk.py, source_mdl.py, vtf.py, convert.write_model)
  out: _p2/w_portalgun.owpg, _gen/gamedata/meshes/portal_mod/wpn_portalgun.ogf,
       _gen/gamedata/textures/portal_mod/<texture>.dds        (never committed: Valve's model and textures)
One bone, wpn_body (MT_SKELETON_RIGID: no motions), every vertex in the bind pose. The bone's box shape is the mesh's
bounds - the physics shell of a dropped gun is built from it. The muzzle points along +Z, as X-Ray's guns.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
CONV = Path(r"E:\github\universal-modder\examples\outer-wilds-portal-gun\tools")
sys.path.insert(0, str(CONV))
import owpg  # noqa: E402
from p2_assets import PORTAL2  # noqa: E402
from make_icons import write_dds_bgra  # noqa: E402
from p2_gun_ogf import (OGF_HEADER, OGF_TEXTURE, OGF_VERTICES, OGF_INDICES, OGF_CHILDREN, OGF_S_BONE_NAMES,  # noqa: E402
                        OGF_S_IKDATA, MT_SKELETON_GEOMDEF_ST, VF_3W, chunk, sz, header)

MT_SKELETON_RIGID = 10
MDL = "models/weapons/w_portalgun"
OWPG = ROOT / "_p2" / "w_portalgun.owpg"
OUT = ROOT / "_gen" / "gamedata" / "meshes" / "portal_mod" / "wpn_portalgun.ogf"
TEX_OUT = ROOT / "_gen" / "gamedata" / "textures" / "portal_mod"
SHADER = "models\\model"
MASS = 2.5  # kg, the gun dropped
ORIENT = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=np.float64)  # owpg -> X-Ray (x right, y up, z muzzle)


def source_fs():
    from vpk import SourceFS
    p2 = Path(PORTAL2)
    return SourceFS([str(p2 / d / "pak01_dir.vpk") for d in ("portal2_dlc2", "portal2_dlc1", "portal2")]
                    + [str(p2 / "portal2")])


def extract(fs):
    """The model to _p2/w_portalgun.owpg, its textures as .dds; {model texture name: X-Ray texture path}."""
    import convert
    import vtf
    from source_mdl import Model
    m = Model(fs.read(MDL + ".mdl"), fs.read(MDL + ".vvd"), fs.read(MDL + ".dx90.vtx"))
    log = {"textures": [], "sounds": [], "missing": []}
    convert.write_model(m, str(OWPG), log)
    names = {}
    for tex in m.textures:
        vmt = None
        for cd in m.cdtextures:
            vmt = fs.read("materials/" + (cd + tex).replace("\\", "/").lower() + ".vmt")
            if vmt:
                break
        base = None
        if vmt:
            hit = re.search(rb'"?\$basetexture"?\s+"?([^"\r\n]+)"?', vmt, re.I)
            base = hit.group(1).decode("latin-1").strip().replace("\\", "/") if hit else None
        data = fs.read("materials/" + base.lower() + ".vtf") if base else None
        if data is None:
            print("texture not found:", tex, base)
            continue
        out = Path(base).name.lower()
        TEX_OUT.mkdir(parents=True, exist_ok=True)
        write_dds_bgra(vtf.decode(data).convert("RGBA"), TEX_OUT / f"{out}.dds")
        names[tex.lower()] = "portal_mod\\" + out
        print("texture", tex, "<-", base)
    return names


def build(names):
    m = owpg.load(OWPG)
    # the converter's world model lies on its side: up along x, the claws (the muzzle) along y. A turn (no mirror) to
    # X-Ray's x right, y up, z muzzle - read off shaded views of the mesh
    P = np.array(m.pos, dtype=np.float64) @ ORIENT.T
    N = np.array(m.nrm, dtype=np.float64) @ ORIENT.T
    lo, hi = P.min(0), P.max(0)

    # ---- one bone, wpn_body at the origin; its box is the mesh's bounds
    bn = struct.pack("<I", 1) + sz("wpn_body") + sz("") + struct.pack("<9f3f3f", 1, 0, 0, 0, 1, 0, 0, 0, 1,
                                                                        *((lo + hi) / 2), *((hi - lo) / 2))
    box = struct.pack("<9f3f3f", 1, 0, 0, 0, 1, 0, 0, 0, 1, *((lo + hi) / 2), *((hi - lo) / 2))
    ik = struct.pack("<I", 1) + sz("default_object")
    ik += struct.pack("<HH", 1, 0) + box + b"\0" * 16 + b"\0" * 32  # SBoneShape: box
    ik += struct.pack("<I", 0) + struct.pack("<12f", *([0, 0, 1, 1] * 3))  # SJointIKData: rigid
    ik += struct.pack("<2fI3f", 1, 1, 0, 0, 0, 0)
    ik += struct.pack("<3f3f", 0, 0, 0, 0, 0, 0)
    ik += struct.pack("<f3f", MASS, *((lo + hi) / 2))

    children = b""
    for ci, (tex, tris) in enumerate(m.submeshes):
        used = np.unique(tris.reshape(-1))
        remap = -np.ones(len(P), dtype=np.int64)
        remap[used] = np.arange(len(used))
        t = remap[tris]
        Pu, Nu, UV = P[used], N[used], m.uv[used]
        T = np.cross(Nu, [0.0, 1.0, 0.0]) + 1e-6
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        B = np.cross(Nu, T)
        verts = bytearray(struct.pack("<II", VF_3W, len(used)))
        for v in range(len(used)):
            verts += struct.pack("<3H12f2f2f", 0, 0, 0, *Pu[v], *Nu[v], *T[v], *B[v], 1.0, 0.0, UV[v][0], UV[v][1])
        idx = struct.pack("<I", t.size) + struct.pack(f"<{t.size}H", *t.reshape(-1).tolist())
        child = chunk(OGF_HEADER, header(MT_SKELETON_GEOMDEF_ST, Pu))
        child += chunk(OGF_TEXTURE, sz(names.get(tex.lower(), "portal_mod\\" + tex.lower())) + sz(SHADER))
        child += chunk(OGF_VERTICES, bytes(verts)) + chunk(OGF_INDICES, idx)
        children += chunk(ci, child)

    ogf = chunk(OGF_HEADER, header(MT_SKELETON_RIGID, P))
    ogf += chunk(OGF_CHILDREN, children)
    ogf += chunk(OGF_S_BONE_NAMES, bn)
    ogf += chunk(OGF_S_IKDATA, ik)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(ogf)
    print(f"wrote {OUT} ({len(ogf) / 1024:.0f} KB): {len(m.submeshes)} meshes, {len(P)} verts, "
          f"size {hi - lo} m (x right, y up, z muzzle), centre {(lo + hi) / 2}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--info", action="store_true", help="only list the model's files and textures in the VPKs")
    args = ap.parse_args()
    fs = source_fs()
    if args.info:
        for k in fs.find("w_portalgun"):
            print(k)
        return
    build(extract(fs))


if __name__ == "__main__":
    main()
