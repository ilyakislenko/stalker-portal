"""Run the game on a lab profile under _lab/ (logs, saves, user.ltx), so tests never touch the real profile.

  python -I tools/lab.py --save all [--res 1280x720] [--timeout 240]

- _lab/fsgame.ltx: the game's fsgame.ltx with $app_data_root$ pointed at _lab/appdata/
- copies the chosen save (.sav + .dds) and user.ltx from the real profile (read-only there)
- starts bin_x64/xrEngine.exe -fsltx <lab fsgame> -nointro -start server(<save>/single/alife/load) client(localhost), cwd = game root
- waits for exit / AUTOTEST RESULT / timeout, then prints the [portal_mod] lines and script errors
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = Path(r"E:\Games\S.T.A.L.K.E.R. Shadow of Chernobyl")
REAL = Path(r"C:\Users\User\docume~1\stalke~3")
LAB = ROOT / "_lab"
APPDATA = LAB / "appdata"
ERR = re.compile(r"\[portal_mod\]|SCRIPT ERROR|LUA error|attempt to|stack traceback|FATAL|Expression|ExceptionCode|cannot open|not found|Can't find section", re.I)
NOISE = re.compile(r"Can't find texture|ParticleEffect|cant find corresponding|GetActionAllBinding|Renderer doesn't support|VOTE", re.I)


def prepare(save, res):
    for d in ("savedgames", "logs", "screenshots"):
        (APPDATA / d).mkdir(parents=True, exist_ok=True)
    fs = (GAME / "fsgame.ltx").read_text(encoding="cp1251")
    fs = re.sub(r"(?m)^(\$app_data_root\$\s*=\s*[^|]*\|[^|]*\|\s*).*$", lambda m: m.group(1) + str(APPDATA) + "\\", fs)
    (LAB / "fsgame.ltx").write_text(fs, encoding="cp1251", newline="\r\n")
    user = (REAL / "user.ltx").read_text(encoding="cp1251")
    user = re.sub(r"(?m)^vid_mode .*$", f"vid_mode {res}", user)
    # no "press any key" after loading: tests must run unattended
    user = re.sub(r"(?m)^keypress_on_start .*\n?", "", user).rstrip("\n") + "\nkeypress_on_start off\n"
    # keep simulating when the window is in the background (else physics stops while scripts still tick)
    user = re.sub(r"(?m)^rs_always_active .*\n?", "", user).rstrip("\n") + "\nrs_always_active on\n"
    (APPDATA / "user.ltx").write_text(user, encoding="cp1251", newline="\r\n")
    for ext in (".sav", ".dds"):
        src = REAL / "savedgames" / (save + ext)
        if src.exists():
            shutil.copy2(src, APPDATA / "savedgames" / src.name)
    if not (APPDATA / "savedgames" / (save + ".sav")).exists():
        sys.exit(f"save not found: {save}")


UM_ROOT = Path(r"E:\github\universal-modder")
UM_PY = UM_ROOT / ".venv" / "Scripts" / "python.exe"
UM_ENV = {"LOCALAPPDATA": r"E:\tools\um-local", "UV_CACHE_DIR": r"E:\github\.uv-cache"}  # ffmpeg + capture tools live on E:
UM_FFMPEG_BIN = r"E:\tools\um-local\universal-modder\ffmpeg\bin"
VIDEOS = ROOT / "_videos"


def um(*args, **kw):
    import os
    env = dict(os.environ, **UM_ENV)
    env["PATH"] = UM_FFMPEG_BIN + ";" + env.get("PATH", "")  # `um video` calls plain ffmpeg
    return subprocess.Popen([str(UM_PY), "-m", "um", *args], cwd=str(UM_ROOT), env=env, text=True, encoding="utf-8", errors="replace", **kw)


def newest_log(after):
    logs = [p for p in (APPDATA / "logs").glob("xray_*.log") if p.stat().st_mtime >= after]
    return max(logs, key=lambda p: p.stat().st_mtime) if logs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="all")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--engine", default="bin_x64", help="engine folder in the game dir: bin_x64 (stock OGSR) or bin_portal (our build)")
    ap.add_argument("--record", metavar="TAKE", help="record the game window + game-only audio to _videos/TAKE.mp4 "
                    "(starts at 'AUTOTEST armed', stops 4.5 s after the result)")
    a = ap.parse_args()
    prepare(a.save, a.res)
    t0 = time.time() - 1
    # "-load <save>" runs the load before the device exists and crashes (OGSR 3.518); "start" is deferred.
    cmd = [str(GAME / a.engine / "xrEngine.exe"), "-fsltx", str(LAB / "fsgame.ltx"), "-nointro",
           "-start", f"server({a.save}/single/alife/load)", "client(localhost)"]
    proc = subprocess.Popen(cmd, cwd=str(GAME))
    print(f"started pid {proc.pid}: {' '.join(cmd)}", flush=True)
    if a.no_wait:
        return
    result = "timeout"
    rec = None
    base = None
    while time.time() - t0 < a.timeout:
        if proc.poll() is not None:
            result = f"exited with code {proc.returncode}"
            break
        log = newest_log(t0)
        text = log.read_text(encoding="cp1251", errors="replace") if log else ""
        if a.record and rec is None and "AUTOTEST armed" in text:
            VIDEOS.mkdir(exist_ok=True)
            base = str(VIDEOS / a.record)
            rec = um("win", "record", "--exe", "xrEngine.exe", "--pid", str(proc.pid), "--out", base,
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(f"recording -> {base}.mkv", flush=True)
        if "AUTOTEST RESULT" in text:
            result = "autotest finished"
            time.sleep(4.5)
            break
        time.sleep(0.5)
    if rec:
        out, _ = rec.communicate("\n", timeout=60)
        print(out.strip()[-800:], flush=True)
        mux = um("video", "mux", base + ".mkv", base + ".audio.raw", base + ".json", base + ".mp4",
                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(mux.communicate(timeout=300)[0].strip()[-800:], flush=True)
    if proc.poll() is None:
        time.sleep(3)
    print(f"--- {result} after {time.time() - t0:.0f}s", flush=True)
    log = newest_log(t0)
    if not log:
        print("no log written")
        return
    print(f"--- {log}")
    for line in log.read_text(encoding="cp1251", errors="replace").splitlines():
        if ERR.search(line) and not NOISE.search(line):
            print(line)


if __name__ == "__main__":
    main()
