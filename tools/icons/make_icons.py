"""Draws the Windows icons of MM Core (standard library only) into icons/*.ico:
mm_core.ico (one-click start), mm_logon.ico (MM Core Logon), mm_dashboard.ico
(MM Core Dashboard). Every icon holds 16 ... 256 px PNG images, drawn with
4x4 supersampling.   python tools/icons/make_icons.py"""
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "icons")
SIZES = (16, 24, 32, 48, 64, 128, 256)
NAVY, BLUE, GREEN, ORANGE, VIOLET, WHITE = ((28, 43, 74), (47, 128, 237), (39, 174, 96), (242, 153, 74),
                                            (155, 81, 224), (255, 255, 255))


def rrect(x, y, x0, y0, x1, y1, r):
    """inside a rounded rectangle (unit coordinates 0..1)."""
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def seg(x, y, ax, ay, bx, by, w):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= (w / 2) ** 2


def ring_color(x, y, cx, cy, r0, r1, parts):
    d = math.hypot(x - cx, y - cy)
    if not r0 <= d <= r1:
        return None
    a = (math.atan2(y - cy, x - cx) + math.pi / 2) % (2 * math.pi) / (2 * math.pi)
    acc = 0
    for frac, col in parts:
        acc += frac
        if a <= acc:
            return col
    return parts[-1][1]


def dashboard(x, y):
    if not rrect(x, y, 0.03, 0.03, 0.97, 0.97, 0.2):
        return None
    for i, (h, col) in enumerate(((0.26, BLUE), (0.40, GREEN), (0.54, ORANGE))):
        x0 = 0.14 + i * 0.12
        if rrect(x, y, x0, 0.84 - h, x0 + 0.085, 0.84, 0.02):
            return col
    c = ring_color(x, y, 0.72, 0.31, 0.075, 0.165, ((0.45, BLUE), (0.25, GREEN), (0.18, ORANGE), (0.12, VIOLET)))
    if c:
        return c
    if (seg(x, y, 0.55, 0.80, 0.66, 0.66, 0.05) or seg(x, y, 0.66, 0.66, 0.74, 0.73, 0.05)
            or seg(x, y, 0.74, 0.73, 0.86, 0.56, 0.05)):
        return WHITE
    return NAVY


def core(x, y):
    if not rrect(x, y, 0.03, 0.03, 0.97, 0.97, 0.2):
        return None
    w = 0.11
    if (seg(x, y, 0.25, 0.72, 0.25, 0.30, w) or seg(x, y, 0.25, 0.30, 0.50, 0.52, w)
            or seg(x, y, 0.50, 0.52, 0.75, 0.30, w) or seg(x, y, 0.75, 0.30, 0.75, 0.72, w)):
        return WHITE
    return BLUE


def logon(x, y):
    if not rrect(x, y, 0.03, 0.03, 0.97, 0.97, 0.2):
        return None
    if rrect(x, y, 0.18, 0.20, 0.82, 0.64, 0.05):
        if rrect(x, y, 0.23, 0.25, 0.77, 0.59, 0.02):
            if rrect(x, y, 0.40, 0.40, 0.60, 0.55, 0.02) or (math.hypot(x - 0.5, y - 0.40) <= 0.08 and
                                                           math.hypot(x - 0.5, y - 0.40) >= 0.045 and y <= 0.40):
                return ORANGE
            return BLUE
        return WHITE
    if rrect(x, y, 0.44, 0.64, 0.56, 0.74, 0.0) or rrect(x, y, 0.32, 0.74, 0.68, 0.80, 0.02):
        return WHITE
    return NAVY


def render(fn, n, ss=4):
    rows = []
    for py in range(n):
        row = bytearray([0])
        for px in range(n):
            r = g = b = a = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = fn((px + (sx + 0.5) / ss) / n, (py + (sy + 0.5) / ss) / n)
                    if c:
                        r, g, b, a = r + c[0], g + c[1], b + c[2], a + 1
            k = ss * ss
            row += bytes((r // a, g // a, b // a, 255 * a // k) if a else (0, 0, 0, 0))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def ico(fn, path):
    pngs = [render(fn, n) for n in SIZES]
    head = struct.pack("<HHH", 0, 1, len(pngs))
    off = 6 + 16 * len(pngs)
    dirs, data = b"", b""
    for n, p in zip(SIZES, pngs):
        dirs += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(p), off + len(data))
        data += p
    with open(path, "wb") as f:
        f.write(head + dirs + data)
    with open(path.replace(".ico", ".png"), "wb") as f:
        f.write(pngs[-1])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("mm_dashboard", dashboard), ("mm_core", core), ("mm_logon", logon)):
        ico(fn, os.path.join(OUT, name + ".ico"))
        print("wrote", os.path.join(OUT, name + ".ico"))
