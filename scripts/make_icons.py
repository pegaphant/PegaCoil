"""Erzeugt resources/16x16.png, 32x32.png, 64x64.png (+ @2x) – grüne Scheibe mit Kupferspulen."""

import math
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(__file__), '..', 'resources')


def png(path, size):
    rows = []
    c = (size - 1) / 2
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx, dy = (x - c) / c, (c - y) / c
            r = math.hypot(dx, dy)
            px = (0, 0, 0, 0)
            if 0.28 <= r <= 0.98:
                px = (22, 92, 52, 255)
                t = math.atan2(dy, dx) % (2 * math.pi / 6)
                if 0.4 < r < 0.85 and 0.08 < t < 2 * math.pi / 6 - 0.08:
                    # Sektorspule als Rahmen
                    edge = min(r - 0.4, 0.85 - r, (t - 0.08) * r, (2 * math.pi / 6 - 0.08 - t) * r)
                    if (edge * size) % 3.2 < 1.6:
                        px = (214, 130, 60, 255)
            row += bytes(px)
        rows.append(bytes(row))
    raw = b''.join(rows)

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(data)


os.makedirs(OUT, exist_ok=True)
for s in (16, 32, 64):
    png(os.path.join(OUT, f'{s}x{s}.png'), s)
    png(os.path.join(OUT, f'{s}x{s}@2x.png'), 2 * s)
