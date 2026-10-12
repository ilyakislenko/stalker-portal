"""Unpack files from S.T.A.L.K.E.R. (X-Ray) .db/.xdb archives of the user's own install.

Format ported from OGSR Engine (xrCore/arc_db.cpp, trivial_encryptor.cpp, LzHuf.cpp, rt_compressor.cpp):
  archive  = chunks of (u32 type, u32 size, data); chunk 1 = file list, bit 31 of type = LZHUF-compressed
  SoC .db  = file-list chunk is also encrypted (trivial_encryptor, WW key, then RU key as fallback)
  entry    = u16 len, then [u32 size_real, u32 size_compressed, u32 crc, name, u32 ptr]
  data     = raw when size_real == size_compressed, otherwise LZO1X

  python -I xrdb_unpack.py <game_dir> <out_dir> [--only config\\ scripts\\ ...] [--list]
Later archives override earlier ones (same order the engine mounts them).
"""
import argparse
import re
import struct
import sys
from pathlib import Path

CFS_COMPRESS_MARK = 1 << 31

# ---------------------------------------------------------------- trivial_encryptor
KEY_WW = (1024, 6011979, 24031979)   # table iterations, table seed, encrypt seed
KEY_RU = (2048, 20091958, 20031955)


class _Rand32:
    def __init__(self, seed):
        self.seed = seed & 0xFFFFFFFF

    def random(self, rng):
        self.seed = (0x08088405 * self.seed + 1) & 0xFFFFFFFF
        return (self.seed * rng) >> 32


def _alphabet_back(key):
    iters, table_seed, _ = key
    alpha = list(range(256))
    r = _Rand32(table_seed)
    for _ in range(iters):
        j = r.random(256)
        k = r.random(256)
        while j == k:
            k = r.random(256)
        alpha[j], alpha[k] = alpha[k], alpha[j]
    back = [0] * 256
    for i, a in enumerate(alpha):
        back[a] = i
    return back


def decrypt(data, key):
    back = _alphabet_back(key)
    r = _Rand32(key[2])
    return bytes(back[b ^ (r.random(256) & 0xFF)] for b in data)


# ---------------------------------------------------------------- LZHUF (header chunk)
N, F, THRESHOLD = 4096, 60, 2
N_CHAR = 256 - THRESHOLD + F
T = N_CHAR * 2 - 1
R = T - 1
MAX_FREQ = 0x4000


def _load_tables():
    src = (Path(__file__).resolve().parent.parent / "docs" / "ogsr-ref" / "LzHuf.cpp").read_text(encoding="utf-8", errors="replace")

    def arr(name):
        m = re.search(r"\b" + name + r"\s*\[[^\]]*\]\s*=\s*\{(.*?)\}", src, re.S)
        if not m:
            sys.exit(f"table {name} not found in LzHuf.cpp")
        return [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\d+", m.group(1))]

    d_code, d_len = arr("d_code"), arr("d_len")
    assert len(d_code) == 256 and len(d_len) == 256, (len(d_code), len(d_len))
    return d_code, d_len


def lzhuf_decode(src, total_size):
    """Returns bytes or None (the engine's 'decode failed' -> try another key)."""
    if len(src) < 4:
        return None
    textsize = struct.unpack_from("<I", src, 0)[0]
    if textsize == 0 or textsize > total_size:
        return None
    d_code, d_len = D_TABLES
    pos = 4
    n = len(src)
    getbuf = 0
    getlen = 0

    freq = [0] * (T + 1)
    son = [0] * T
    prnt = [0] * (T + N_CHAR)
    for i in range(N_CHAR):
        freq[i] = 1
        son[i] = i + T
        prnt[i + T] = i
    i, j = 0, N_CHAR
    while j <= R:
        freq[j] = freq[i] + freq[i + 1]
        son[j] = i
        prnt[i] = prnt[i + 1] = j
        i += 2
        j += 1
    freq[T] = 0xFFFF
    prnt[R] = 0

    def reconst():
        j = 0
        for i in range(T):
            if son[i] >= T:
                freq[j] = (freq[i] + 1) // 2
                son[j] = son[i]
                j += 1
        i, j = 0, N_CHAR
        while j < T:
            f = freq[j] = freq[i] + freq[i + 1]
            k = j - 1
            while f < freq[k]:
                k -= 1
            k += 1
            freq[k + 1:j + 1] = freq[k:j]
            freq[k] = f
            son[k + 1:j + 1] = son[k:j]
            son[k] = i
            i += 2
            j += 1
        for i in range(T):
            k = son[i]
            if k >= T:
                prnt[k] = i
            else:
                prnt[k] = prnt[k + 1] = i

    def update(c):
        if freq[R] == MAX_FREQ:
            reconst()
        c = prnt[c + T]
        while True:
            freq[c] += 1
            k = freq[c]
            l = c + 1
            if k > freq[l]:
                l += 1
                while k > freq[l]:
                    l += 1
                l -= 1
                freq[c] = freq[l]
                freq[l] = k
                i = son[c]
                prnt[i] = l
                if i < T:
                    prnt[i + 1] = l
                j = son[l]
                son[l] = i
                prnt[j] = c
                if j < T:
                    prnt[j + 1] = c
                son[c] = j
                c = l
            c = prnt[c]
            if c == 0:
                break

    out = bytearray()
    text_buf = bytearray(b" " * (N - F) + b"\0" * F)
    r = N - F
    count = 0
    while count < textsize:
        # DecodeChar
        c = son[R]
        while c < T:
            while getlen <= 8:
                b = src[pos] if pos < n else 0
                pos += 1
                getbuf |= b << (8 - getlen)
                getlen += 8
            bit = (getbuf >> 15) & 1
            getbuf = (getbuf << 1) & 0xFFFF
            getlen -= 1
            c = son[c + bit]
        c -= T
        update(c)
        if c < 256:
            out.append(c)
            text_buf[r] = c
            r = (r + 1) & (N - 1)
            count += 1
        else:
            # DecodePosition
            while getlen <= 8:
                b = src[pos] if pos < n else 0
                pos += 1
                getbuf |= b << (8 - getlen)
                getlen += 8
            i = (getbuf >> 8) & 0xFF
            getbuf = (getbuf << 8) & 0xFFFF
            getlen -= 8
            cc = d_code[i] << 6
            jj = d_len[i] - 2
            while jj > 0:
                jj -= 1
                while getlen <= 8:
                    b = src[pos] if pos < n else 0
                    pos += 1
                    getbuf |= b << (8 - getlen)
                    getlen += 8
                bit = (getbuf >> 15) & 1
                getbuf = (getbuf << 1) & 0xFFFF
                getlen -= 1
                i = (i << 1) + bit
            p = cc | (i & 0x3F)
            start = (r - p - 1) & (N - 1)
            for k in range(c - 255 + THRESHOLD):
                ch = text_buf[(start + k) & (N - 1)]
                out.append(ch)
                text_buf[r] = ch
                r = (r + 1) & (N - 1)
                count += 1
    return bytes(out)


# ---------------------------------------------------------------- LZO1X (file data)
def lzo1x_decompress(src, out_len):
    out = bytearray()
    ip = 0

    def copy_match(m_pos, length):
        for _ in range(length):  # byte by byte: matches may overlap the output
            out.append(out[m_pos])
            m_pos += 1

    def ext_len(base):
        nonlocal ip
        t = 0
        while src[ip] == 0:
            t += 255
            ip += 1
        t += base + src[ip]
        ip += 1
        return t

    state = "loop"
    t = 0
    if src[0] > 17:
        t = src[0] - 17
        ip = 1
        if t < 4:
            state = "match_next"
        else:
            out += src[ip:ip + t]
            ip += t
            state = "first_literal_run"

    while True:
        if state == "loop":
            t = src[ip]
            ip += 1
            if t >= 16:
                state = "match"
                continue
            if t == 0:
                t = ext_len(15)
            out += src[ip:ip + t + 3]
            ip += t + 3
            state = "first_literal_run"
        if state == "first_literal_run":
            t = src[ip]
            ip += 1
            if t >= 16:
                state = "match"
            else:
                m_pos = len(out) - (1 + 0x0800) - (t >> 2) - (src[ip] << 2)
                ip += 1
                copy_match(m_pos, 3)
                state = "match_done"
        if state == "match":
            if t >= 64:
                m_pos = len(out) - 1 - ((t >> 2) & 7) - (src[ip] << 3)
                ip += 1
                copy_match(m_pos, (t >> 5) - 1 + 2)
            elif t >= 32:
                t &= 31
                if t == 0:
                    t = ext_len(31)
                m_pos = len(out) - 1 - ((src[ip] | (src[ip + 1] << 8)) >> 2)
                ip += 2
                copy_match(m_pos, t + 2)
            elif t >= 16:
                m_pos = len(out) - ((t & 8) << 11)
                t &= 7
                if t == 0:
                    t = ext_len(7)
                m_pos -= (src[ip] | (src[ip + 1] << 8)) >> 2
                ip += 2
                if m_pos == len(out):
                    break  # end of stream
                m_pos -= 0x4000
                copy_match(m_pos, t + 2)
            else:
                m_pos = len(out) - 1 - (t >> 2) - (src[ip] << 2)
                ip += 1
                copy_match(m_pos, 2)
            state = "match_done"
        if state == "match_done":
            t = src[ip - 2] & 3
            if t == 0:
                state = "loop"
                continue
            state = "match_next"
        if state == "match_next":
            out += src[ip:ip + t]
            ip += t
            t = src[ip]
            ip += 1
            state = "match"
    if len(out) != out_len:
        raise ValueError(f"LZO size mismatch {len(out)} != {out_len}")
    return bytes(out)


# ---------------------------------------------------------------- archive
def read_index(path):
    data = path.read_bytes()
    is_xdb = ".xdb" in path.name.lower()
    pos = 0
    while pos + 8 <= len(data):
        typ, size = struct.unpack_from("<II", data, pos)
        body = data[pos + 8:pos + 8 + size]
        pos += 8 + size
        if (typ & ~CFS_COMPRESS_MARK) != 1:
            continue
        hdr = body
        if typ & CFS_COMPRESS_MARK:
            hdr = None
            tries = [KEY_WW, KEY_RU, None] if not is_xdb else [None]
            for key in tries:
                src = decrypt(body, key) if key else body
                hdr = lzhuf_decode(src, len(data))
                if hdr is not None:
                    break
            if hdr is None:
                raise ValueError(f"{path.name}: cannot decode file list")
        entries = []
        p = 0
        while p < len(hdr):
            (blen,) = struct.unpack_from("<H", hdr, p)
            p += 2
            buf = hdr[p:p + blen]
            p += blen
            size_real, size_comp, _crc = struct.unpack_from("<III", buf, 0)
            name = buf[12:blen - 4].decode("cp1251", errors="replace")
            (ptr,) = struct.unpack_from("<I", buf, blen - 4)
            entries.append((name, ptr, size_real, size_comp))
        return data, entries
    raise ValueError(f"{path.name}: no file-list chunk")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--only", nargs="*", default=[], help="path prefixes to extract, e.g. config\\ scripts\\")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    archives = sorted(p for p in Path(a.game_dir).iterdir() if p.is_file() and re.search(r"\.(db[0-9a-z]?|xdb\d*)$", p.name, re.I))
    out_dir = Path(a.out_dir)
    prefixes = [x.lower().replace("/", "\\") for x in a.only]
    total = 0
    for arc in archives:
        data, entries = read_index(arc)
        picked = 0
        for name, ptr, size_real, size_comp in entries:
            if name.endswith("\\") or (size_real == 0 and size_comp == 0 and "." not in name.rsplit("\\", 1)[-1]):
                continue
            if prefixes and not name.lower().startswith(tuple(prefixes)):
                continue
            picked += 1
            if a.list:
                print(f"{arc.name}\t{name}\t{size_real}")
                continue
            raw = data[ptr:ptr + size_comp]
            body = raw if size_real == size_comp else lzo1x_decompress(raw, size_real)
            dst = out_dir / name.replace("\\", "/")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(body)
        print(f"{arc.name}: {len(entries)} entries, {picked} picked", file=sys.stderr)
        total += picked
    print(f"total {total}", file=sys.stderr)


D_TABLES = _load_tables()

if __name__ == "__main__":
    main()
