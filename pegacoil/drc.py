"""Eigene Abstandsprüfung.

KiCad prüft Abstände nur zwischen verschiedenen Netzen – eine Spule ist aber ein einziges Netz,
ein Kurzschluss zwischen zwei Windungen fiele dort nicht auf. Diese Prüfung vergleicht deshalb
alle Bahnstücke einer Lage untereinander (auch innerhalb derselben Bahn) und gegen
Durchkontaktierungen und Pads.
"""

import math

from .layout import ends

TOL = 0.004  # mm, Sehnenfehler der Bogenzerlegung + Rundung


def polyline(path, sag=0.002):
    pts = [ends(path[0])[0]]
    for pr in path:
        if pr[0] == 'L':
            pts.append(pr[2])
        else:
            r, t0, t1 = pr[1], pr[2], pr[3]
            step = 2 * math.acos(max(-1.0, 1 - sag / r)) if r > sag else 0.5
            k = max(1, math.ceil(abs(t1 - t0) / step))
            for i in range(1, k + 1):
                t = t0 + (t1 - t0) * i / k
                pts.append((r * math.cos(t), r * math.sin(t)))
    return pts


def _pseg(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def seg_dist(a, b, c, d):
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    # Echte Kreuzung nur bei deutlichen Vorzeichen – Strecken auf einer Geraden liefern sonst
    # Rundungsrauschen mit wechselndem Vorzeichen und würden als Kreuzung gelten.
    eps = 1e-9 * (math.dist(a, b) * math.dist(c, d) + 1e-12)
    if min(abs(d1), abs(d2), abs(d3), abs(d4)) > eps and (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0):
        return 0.0
    return min(_pseg(a, c, d), _pseg(b, c, d), _pseg(c, a, b), _pseg(d, a, b))


def check(layout, coils=None, limit=20):
    """Liste von Fehlertexten (leer = in Ordnung). `coils`: nur diese Spulen (+ Bögen) prüfen."""
    d = layout.design
    g = d.geo
    s = g.s
    errors = []
    cell = max(0.5, 2 * (g.w + s))

    def keep(coil):
        return coils is None or coil in coils or coil == -1

    holes = [(v.x, v.y, g.vr, v.net) for v in layout.vias if keep(v.coil)]
    holes += [(p.x, p.y, g.pad_r, p.net) for p in layout.pads if keep(p.coil)]
    # Durchkontaktierungen/Pads untereinander
    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            a, b = holes[i], holes[j]
            gap = math.hypot(a[0] - b[0], a[1] - b[1]) - a[2] - b[2]
            if gap < s - TOL:
                errors.append(f'Bohrungen zu nah ({gap:.3f} mm) bei ({a[0]:.2f}, {a[1]:.2f})')
    for layer in range(g.n):
        segs = []  # (a, b, halbe Breite, Bahn-Nr., s0, s1)
        tracks = [t for t in layout.tracks if t.layer == layer and keep(t.coil)]
        conn = []
        for ti, t in enumerate(tracks):
            pts = polyline(t.path)
            acc = 0.0
            for a, b in zip(pts, pts[1:]):
                L = math.dist(a, b)
                segs.append((a, b, t.width / 2, ti, acc, acc + L))
                acc += L
            # verbunden: Bahn endet in der Bohrung oder läuft durch ihre Mitte (gleiches Netz)
            conn.append({
                h for h, (x, y, r, net) in enumerate(holes)
                if net == t.net and min(_pseg((x, y), a, b) for a, b in zip(pts, pts[1:])) < r
            })
        grid = {}
        for si, (a, b, hw, _, _, _) in enumerate(segs):
            for gx in range(math.floor(min(a[0], b[0]) / cell), math.floor(max(a[0], b[0]) / cell) + 1):
                for gy in range(math.floor(min(a[1], b[1]) / cell), math.floor(max(a[1], b[1]) / cell) + 1):
                    grid.setdefault((gx, gy), []).append(si)
        seen = set()
        for key, items in grid.items():
            near = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near += grid.get((key[0] + dx, key[1] + dy), [])
            for i in items:
                a, b, hw, ti, s0, s1 = segs[i]
                for j in near:
                    if j <= i or (i, j) in seen:
                        continue
                    seen.add((i, j))
                    c, e, hw2, tj, t0, t1 = segs[j]
                    if ti == tj and (t0 - s1 < 3 * (g.w + s) and s0 - t1 < 3 * (g.w + s)):
                        continue
                    gap = seg_dist(a, b, c, e) - hw - hw2
                    if gap < s - TOL:
                        errors.append(f'Lage {layer + 1}: Bahnen zu nah ({gap:.3f} mm) bei ({a[0]:.2f}, {a[1]:.2f})')
                        if len(errors) >= limit:
                            return errors
        for hi, (x, y, r, _) in enumerate(holes):
            for gx in range(math.floor((x - r) / cell) - 1, math.floor((x + r) / cell) + 2):
                for gy in range(math.floor((y - r) / cell) - 1, math.floor((y + r) / cell) + 2):
                    for si in grid.get((gx, gy), []):
                        a, b, hw, ti, _, _ = segs[si]
                        if hi in conn[ti]:
                            continue
                        gap = _pseg((x, y), a, b) - hw - r
                        if gap < s - TOL:
                            errors.append(f'Lage {layer + 1}: Bahn zu nah an Bohrung ({gap:.3f} mm) bei ({x:.2f}, {y:.2f})')
                            if len(errors) >= limit:
                                return errors
        # Kanten
        r_in = d.p.inner_d / 2
        r_out = d.p.outer_d / 2
        for a, b, hw, _, _, _ in segs:
            for q in (a, b):
                rr = math.hypot(*q)
                if rr - hw < r_in + d.p.edge_clear - TOL or rr + hw > r_out - 0.3 + TOL:
                    errors.append(f'Lage {layer + 1}: Bahn zu nah am Rand bei ({q[0]:.2f}, {q[1]:.2f})')
                    return errors
    return errors
