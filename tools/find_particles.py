"""Search the game's particle effect/group names: python -I tools/find_particles.py glow art [--all]"""
import sys
from pathlib import Path

NAMES = Path(__file__).resolve().parent.parent / "_vanilla" / "particle_names.txt"
words = [w.lower() for w in sys.argv[1:] if not w.startswith("--")]
for line in NAMES.read_text(encoding="utf-8").splitlines():
    kind, name = line.split("\t")
    if all(w in name.lower() for w in words):
        print(kind, name)
