"""Minimal QR code encoder (ISO/IEC 18004), standard library only: byte mode, error
correction level M, versions 1 - 10 (up to 213 bytes), automatic mask. Used for the
pairing link of the mobile dashboard (scan with the phone camera)."""

# version: (EC codewords per block, [(number of blocks, data codewords per block), ...]) - level M
_M = {1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
      6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
      10: (26, [(4, 43), (1, 44)])}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
          9: [6, 26, 46], 10: [6, 28, 50]}

# GF(256) with the polynomial x^8 + x^4 + x^3 + x^2 + 1
_EXP, _LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def rs_ecc(data, n):
    """Reed-Solomon error correction codewords (n of them) for the data codewords."""
    gen = [1]
    for i in range(n):                              # (x - a^0)(x - a^1)...(x - a^(n-1))
        nxt = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _mul(g, _EXP[i])
        gen = nxt
    rem = [0] * n
    for d in data:
        f = d ^ rem[0]
        rem = rem[1:] + [0]
        for j in range(n):
            rem[j] ^= _mul(gen[j + 1], f)
    return rem


def _codewords(data, ver):
    ec, groups = _M[ver]
    cap = sum(n * k for n, k in groups)
    bits = []

    def put(v, n):
        bits.extend((v >> (n - 1 - i)) & 1 for i in range(n))
    put(0b0100, 4)
    put(len(data), 8 if ver < 10 else 16)
    for b in data:
        put(b, 8)
    put(0, min(4, cap * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(cw) < cap:
        cw.append(pad)
        pad ^= 0xEC ^ 0x11
    blocks, pos = [], 0
    for n, k in groups:
        for _ in range(n):
            blocks.append(cw[pos:pos + k])
            pos += k
    eccs = [rs_ecc(b, ec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out += [b[i] for b in blocks if i < len(b)]
    for i in range(ec):
        out += [e[i] for e in eccs]
    return out


_MASKS = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
          lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
          lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
          lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]


def _penalty(m):
    n, p = len(m), 0
    for lines in (m, [list(c) for c in zip(*m)]):          # N1: runs of 5+ in rows and columns
        for row in lines:
            run, last = 0, None
            for v in row:
                run = run + 1 if v == last else 1
                last = v
                if run == 5:
                    p += 3
                elif run > 5:
                    p += 1
    for y in range(n - 1):                                 # N2: 2x2 blocks
        for x in range(n - 1):
            if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                p += 3
    dark = sum(map(sum, m))                                # N4: balance
    p += abs(dark * 20 - n * n * 10) // (n * n) * 10
    return p


def matrix(text):
    """QR code matrix (list of rows, 1 = dark) for text (UTF-8)."""
    data = text.encode("utf-8")
    ver = next((v for v in range(1, 11) if (sum(n * k for n, k in _M[v][1]) * 8 - 4 - (8 if v < 10 else 16))
                // 8 >= len(data)), None)
    if ver is None:
        raise ValueError("Text too long for a QR code (max. 213 bytes)")
    size = ver * 4 + 17
    mod = [[0] * size for _ in range(size)]
    fun = [[False] * size for _ in range(size)]

    def setf(x, y, v):
        mod[y][x] = 1 if v else 0
        fun[y][x] = True
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):          # finder patterns + separators
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    d = max(abs(dx), abs(dy))
                    setf(x, y, d not in (2, 4))
    for i in range(size):                                          # timing patterns
        if not fun[6][i]:
            setf(i, 6, i % 2 == 0)
        if not fun[i][6]:
            setf(6, i, i % 2 == 0)
    al = _ALIGN[ver]
    for ay in al:                                                  # alignment patterns
        for ax in al:
            if (ax, ay) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setf(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)

    def format_bits(mask):
        d = (0 << 3) | mask                                        # level M = 00
        r = d
        for _ in range(10):
            r = (r << 1) ^ ((r >> 9) * 0x537)
        bits = ((d << 10) | r) ^ 0x5412
        b = [(bits >> i) & 1 for i in range(15)]
        for i in range(6):
            setf(8, i, b[i])
        setf(8, 7, b[6])
        setf(8, 8, b[7])
        setf(7, 8, b[8])
        for i in range(9, 15):
            setf(14 - i, 8, b[i])
        for i in range(8):
            setf(size - 1 - i, 8, b[i])
        for i in range(8, 15):
            setf(8, size - 15 + i, b[i])
        setf(8, size - 8, 1)                                       # dark module
    format_bits(0)                                                 # reserve the areas
    if ver >= 7:
        r = ver
        for _ in range(12):
            r = (r << 1) ^ ((r >> 11) * 0x1F25)
        bits = (ver << 12) | r
        for i in range(18):
            b = (bits >> i) & 1
            a, c = size - 11 + i % 3, i // 3
            setf(a, c, b)
            setf(c, a, b)
    cw = _codewords(data, ver)
    i, total = 0, len(cw) * 8
    right = size - 1
    while right >= 1:                                              # zig-zag placement
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                up = ((right + 1) & 2) == 0
                y = size - 1 - vert if up else vert
                if not fun[y][x] and i < total:
                    mod[y][x] = (cw[i >> 3] >> (7 - (i & 7))) & 1
                    i += 1
        right -= 2
    best = None
    for k, fn in enumerate(_MASKS):
        m = [row[:] for row in mod]
        for y in range(size):
            for x in range(size):
                if not fun[y][x] and fn(x, y):
                    m[y][x] ^= 1
        saved = [row[:] for row in mod], [row[:] for row in fun]
        mod[:] = m
        format_bits(k)
        m = [row[:] for row in mod]
        mod[:], fun[:] = saved
        p = _penalty(m)
        if best is None or p < best[0]:
            best = (p, m)
    return best[1]


def svg(text, scale=6, border=4):
    """QR code as an SVG image (dark modules on white)."""
    m = matrix(text)
    n = len(m) + 2 * border
    path = "".join("M%d,%dh1v1h-1z" % (x + border, y + border) for y, row in enumerate(m)
                   for x, v in enumerate(row) if v)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
            'shape-rendering="crispEdges"><rect width="100%%" height="100%%" fill="#fff"/>'
            '<path fill="#000" d="%s"/></svg>' % (n, n, n * scale, n * scale, path))
