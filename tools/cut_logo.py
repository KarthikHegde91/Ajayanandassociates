"""Cut the approved logo sheet (navy & gold, Sep 2026) into the transparent PNG
assets the site uses. Stdlib only.

usage: python tools/cut_logo.py <logo-sheet.png>

writes src/assets/img/: logo-light.png, logo-dark.png (horizontal lockups for the
header/footer), logo-compact-light/dark.png (stacked lockups), logo-mark.png
(gold mark), logo-tile-light/dark.png (navy app tile), and src/static/favicon.svg.
"""
import base64
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "qa"))
from pngtool import read_png, write_png  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "src", "assets", "img")
STATIC = os.path.join(ROOT, "src", "static")
NAVY = (4, 35, 63)


def load(path):
    w, h, bd, ct, rows, bpp = read_png(path)
    assert bd == 8 and bpp >= 3
    px = [[tuple(r[x * bpp:x * bpp + 3]) for x in range(w)] for r in rows]
    return w, h, px


def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def extract(px, x0, y0, x1, y1, bg, lo=30, hi=90, pad=6):
    """Return (w, h, rgba) of the region with `bg` knocked out to alpha, cropped."""
    rgba = []
    for y in range(y0, y1):
        row = []
        for x in range(x0, x1):
            p = px[y][x]
            d = dist(p, bg)
            a = 0.0 if d <= lo else (1.0 if d >= hi else (d - lo) / (hi - lo))
            if a <= 0:
                row.append((0, 0, 0, 0))
                continue
            fg = tuple(int(min(255, max(0, round((c - (1 - a) * b) / a)))) for c, b in zip(p, bg))
            row.append(fg + (int(round(a * 255)),))
        rgba.append(row)
    return crop(rgba, pad)


def crop(rgba, pad=0):
    h, w = len(rgba), len(rgba[0])
    ys = [y for y in range(h) if any(p[3] > 24 for p in rgba[y])]
    xs = [x for x in range(w) if any(rgba[y][x][3] > 24 for y in range(h))]
    y0, y1 = max(0, ys[0] - pad), min(h, ys[-1] + 1 + pad)
    x0, x1 = max(0, xs[0] - pad), min(w, xs[-1] + 1 + pad)
    out = [r[x0:x1] for r in rgba[y0:y1]]
    return x1 - x0, y1 - y0, out


def empty_rows(rgba):
    return [all(p[3] <= 8 for p in r) for r in rgba]


def split_mark_text(rgba):
    """Split a stacked lockup at the first blank band below the mark."""
    e = empty_rows(rgba)
    y = 0
    while y < len(e) and e[y]:
        y += 1
    while y < len(e) and not e[y]:
        y += 1
    run = y
    while y < len(e) and e[y]:
        y += 1
    assert y - run >= 4, "no blank band between mark and wordmark"
    return crop(rgba[:run], 0), crop(rgba[y:], 0)


def resample(w, h, rgba, nw, nh):
    """Area-averaging resample on premultiplied RGBA."""
    out = []
    sx, sy = w / nw, h / nh
    for j in range(nh):
        y0, y1 = j * sy, (j + 1) * sy
        row = []
        for i in range(nw):
            x0, x1 = i * sx, (i + 1) * sx
            acc = [0.0, 0.0, 0.0, 0.0]
            wsum = 0.0
            for yy in range(int(y0), min(h, int(y1) + 1)):
                wy = min(y1, yy + 1) - max(y0, yy)
                if wy <= 0:
                    continue
                for xx in range(int(x0), min(w, int(x1) + 1)):
                    wx = min(x1, xx + 1) - max(x0, xx)
                    if wx <= 0:
                        continue
                    p = rgba[yy][xx]
                    a = p[3] / 255.0
                    wgt = wx * wy
                    acc[0] += p[0] * a * wgt
                    acc[1] += p[1] * a * wgt
                    acc[2] += p[2] * a * wgt
                    acc[3] += a * wgt
                    wsum += wgt
            if wsum <= 0 or acc[3] <= 0:
                row.append((0, 0, 0, 0))
                continue
            a = acc[3] / wsum
            row.append((int(round(acc[0] / acc[3])), int(round(acc[1] / acc[3])),
                        int(round(acc[2] / acc[3])), int(round(a * 255))))
        out.append(row)
    return nw, nh, out


def canvas(w, h, fill=(0, 0, 0, 0)):
    return [[fill] * w for _ in range(h)]


def blit(dst, src, ox, oy):
    for y, r in enumerate(src):
        for x, p in enumerate(r):
            if p[3] == 0:
                continue
            X, Y = ox + x, oy + y
            if 0 <= X < len(dst[0]) and 0 <= Y < len(dst):
                d = dst[Y][X]
                a = p[3] / 255.0
                da = d[3] / 255.0
                oa = a + da * (1 - a)
                if oa <= 0:
                    continue
                dst[Y][X] = tuple(int(round((p[c] * a + d[c] * da * (1 - a)) / oa)) for c in range(3)) + (int(round(oa * 255)),)


def save(name, w, h, rgba, folder=OUT):
    rows = [b"".join(bytes(p) for p in r) for r in rgba]
    write_png(os.path.join(folder, name), w, rows, 8, 6)
    print(f"{name}: {w}x{h}")


def horizontal(mark, text, gap_ratio=0.16, mark_ratio=1.22):
    (mw, mh, m), (tw, th, t) = mark, text
    nmh = int(round(th * mark_ratio))
    nmw = int(round(mw * nmh / mh))
    _, _, m2 = resample(mw, mh, m, nmw, nmh)
    gap = int(round(th * gap_ratio))
    W, H = nmw + gap + tw, max(nmh, th)
    c = canvas(W, H)
    blit(c, m2, 0, (H - nmh) // 2)
    blit(c, t, nmw + gap, (H - th) // 2)
    return W, H, c


def rounded_tile(size, radius, fill):
    c = canvas(size, size)
    for y in range(size):
        for x in range(size):
            cx = min(max(x + 0.5, radius), size - radius)
            cy = min(max(y + 0.5, radius), size - radius)
            d = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            a = min(1.0, max(0.0, radius - d + 0.5))
            c[y][x] = fill + (int(round(a * 255)),)
    return c


def png_bytes(w, h, rgba):
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in r) for r in rgba)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main(sheet):
    w, h, px = load(sheet)
    y = 30
    navy_x = [x for x in range(w) if dist(px[y][x], NAVY) < 30]
    nx0, nx1 = navy_x[0], navy_x[-1] + 1
    ny1 = 0
    while ny1 < h and dist(px[ny1][nx1 - 12], NAVY) < 30:
        ny1 += 1
    print(f"navy panel x {nx0}-{nx1}, y 0-{ny1}")

    light = extract(px, 0, 0, nx0 - 2, ny1, (253, 253, 253))
    dark = extract(px, nx0 + 2, 2, nx1 - 2, ny1 - 2, NAVY)
    save("logo-compact-light.png", *light)
    save("logo-compact-dark.png", *dark)

    lm, lt = split_mark_text(light[2])
    dm, dt = split_mark_text(dark[2])
    save("logo-mark.png", *lm)
    for name, (W, H, c) in (("logo-light.png", horizontal(lm, lt)), ("logo-dark.png", horizontal(dm, dt))):
        nh = 132  # 3x the 44px header height is plenty
        save(name, *resample(W, H, c, int(round(W * nh / H)), nh))

    size = 512
    tile = rounded_tile(size, 112, NAVY)
    mw, mh, m = lm
    tw = int(size * 0.62)
    th = int(round(mh * tw / mw))
    _, _, m2 = resample(mw, mh, m, tw, th)
    blit(tile, m2, (size - tw) // 2, (size - th) // 2)
    save("logo-tile-light.png", size, size, tile)
    save("logo-tile-dark.png", size, size, tile)

    fw = 160
    fh = int(round(mh * fw / mw))
    _, _, fm = resample(mw, mh, m, fw, fh)
    b64 = base64.b64encode(png_bytes(fw, fh, fm)).decode()
    mx, my = (256 - fw) / 2, (256 - fh) / 2
    navy_hex = "#%02X%02X%02X" % NAVY
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 256 256">\n'
           f'  <rect width="256" height="256" rx="56" fill="{navy_hex}"/>\n'
           f'  <image x="{mx:.1f}" y="{my:.1f}" width="{fw}" height="{fh}" xlink:href="data:image/png;base64,{b64}"/>\n'
           "</svg>\n")
    with open(os.path.join(STATIC, "favicon.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print("favicon.svg written")


if __name__ == "__main__":
    main(sys.argv[1])
