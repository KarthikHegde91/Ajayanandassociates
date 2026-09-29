"""Stdlib-only PNG helpers: read/write, crop, vertical slicing.
usage (slice a tall screenshot): python tools/qa/pngtool.py in.png out_prefix slice_height
"""
import struct, sys, zlib


def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8; idat = b''; w = h = 0; bitdepth = colortype = 0
    while pos < len(d):
        ln, = struct.unpack('>I', d[pos:pos+4]); typ = d[pos+4:pos+8]; data = d[pos+8:pos+8+ln]
        if typ == b'IHDR':
            w, h, bitdepth, colortype = struct.unpack('>IIBB', data[:10])
        elif typ == b'IDAT':
            idat += data
        pos += 12 + ln
    bpp = {2: 3, 6: 4, 0: 1, 4: 2}[colortype] * (bitdepth // 8)
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows = []; prev = bytearray(stride); p = 0
    for _ in range(h):
        f = raw[p]; line = bytearray(raw[p+1:p+1+stride]); p += 1 + stride
        if f == 1:
            for i in range(bpp, stride): line[i] = (line[i] + line[i-bpp]) & 255
        elif f == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0; b = prev[i]; c = prev[i-bpp] if i >= bpp else 0
                pa = abs(b - c); pb = abs(a - c); pc = abs(a + b - 2*c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(bytes(line)); prev = line
    return w, h, bitdepth, colortype, rows, bpp


def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)


def write_png(path, w, rows, bitdepth, colortype):
    bpp = {2: 3, 6: 4, 0: 1, 4: 2}[colortype] * (bitdepth // 8)
    best = None
    for f in (0, 1, 2, 4):  # try a few whole-image filters, keep the smallest
        prev = bytes(len(rows[0]))
        parts = []
        for r in rows:
            r = bytes(r)
            if f == 0: parts.append(b'\x00' + r)
            elif f == 1: parts.append(b'\x01' + bytes((r[i] - (r[i-bpp] if i >= bpp else 0)) & 255 for i in range(len(r))))
            elif f == 2: parts.append(b'\x02' + bytes((r[i] - prev[i]) & 255 for i in range(len(r))))
            else:
                o = bytearray(len(r))
                for i in range(len(r)):
                    a = r[i-bpp] if i >= bpp else 0; b = prev[i]; c = prev[i-bpp] if i >= bpp else 0
                    pa = abs(b - c); pb = abs(a - c); pc = abs(a + b - 2*c)
                    pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    o[i] = (r[i] - pr) & 255
                parts.append(b'\x04' + bytes(o))
            prev = r
        cand = zlib.compress(b''.join(parts), 9)
        if best is None or len(cand) < len(best): best = cand
    out = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, len(rows), bitdepth, colortype, 0, 0, 0))
    out += chunk(b'IDAT', best) + chunk(b'IEND', b'')
    open(path, 'wb').write(out)


if __name__ == '__main__':
    src, prefix, sh = sys.argv[1], sys.argv[2], int(sys.argv[3])
    w, h, bd, ct, rows, bpp = read_png(src)
    last = h - 1
    while last > 0 and rows[last] == rows[h-1]: last -= 1
    rows = rows[:last + 2]
    n = 0
    for y in range(0, len(rows), sh):
        write_png(f'{prefix}-{n}.png', w, rows[y:y+sh], bd, ct); n += 1
    print(f'{n} slices of {w}x{sh} (content height {len(rows)})')
