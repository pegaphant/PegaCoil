"""Leiterbahnen, Durchkontaktierungen und Pads aus einer Auslegung erzeugen.

Grundelemente (alle Bögen um den Plattenmittelpunkt):
  ('L', (x0, y0), (x1, y1))      Gerade
  ('A', r, t0, t1)               Bogen mit Radius r von Winkel t0 nach t1 (t1 > t0 = gegen Uhrzeiger)
"""

import math
from dataclasses import dataclass, field

from .design import PHASES, polar


@dataclass
class Track:
    layer: int  # 0 = oben (F.Cu) … n-1 = unten (B.Cu)
    path: list  # zusammenhängende Grundelemente
    width: float
    net: int  # 1..3 = U, V, W
    coil: int  # Spulennummer, -1 = Verbindungsbogen


@dataclass
class Via:
    x: float
    y: float
    net: int
    coil: int


@dataclass
class Pad:
    x: float
    y: float
    name: str
    net: int
    coil: int


@dataclass
class Layout:
    design: object
    tracks: list = field(default_factory=list)
    vias: list = field(default_factory=list)
    pads: list = field(default_factory=list)
    nets: tuple = PHASES  # Netznamen, Index = net - 1


# --- Transformationen ---------------------------------------------------------


def rot(pt, t):
    c, s = math.cos(t), math.sin(t)
    return (pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c)


def rot_prim(pr, t):
    if pr[0] == 'L':
        return ('L', rot(pr[1], t), rot(pr[2], t))
    return ('A', pr[1], pr[2] + t, pr[3] + t)


def mirror(pr):
    if pr[0] == 'L':
        return ('L', (pr[1][0], -pr[1][1]), (pr[2][0], -pr[2][1]))
    return ('A', pr[1], -pr[2], -pr[3])


def reverse(path):
    out = []
    for pr in reversed(path):
        out.append(('L', pr[2], pr[1]) if pr[0] == 'L' else ('A', pr[1], pr[3], pr[2]))
    return out


def ends(pr):
    if pr[0] == 'L':
        return pr[1], pr[2]
    return polar(pr[1], pr[2]), polar(pr[1], pr[3])


def prim_length(pr):
    if pr[0] == 'L':
        return math.dist(pr[1], pr[2])
    return pr[1] * abs(pr[3] - pr[2])


def path_length(path):
    return sum(prim_length(pr) for pr in path)


# --- eine Spule (lokal) ----------------------------------------------------------


def mpt(p):
    return (p[0], -p[1])


def corner(g, k, which):
    d, dl = g.d(k), g.dl(k)
    rho = g.r2 - d if which[0] == 'T' else g.r1 + d
    p = g.pt(rho, dl)
    return mpt(p) if which[1] == 'M' else p


def spiral_in(g, N, j, rv):
    """Lage mit Lauf nach innen (Uhrzeigersinn) von TP_0 bis zur inneren Durchkontaktierung j."""
    # Windungswechsel als Absatz an der Ecke TP: die P-Flanke läuft gerade bis unter die
    # obere Kante der nächsten Windung, der obere Bogen der nächsten Windung beginnt dort.
    path = []
    for k in range(N):
        d, dl = g.d(k), g.dl(k)
        rt, rb = g.r2 - d, g.r1 + d
        at, ab = g.ang(rt, dl), g.ang(rb, dl)
        start = at if k == 0 else g.ang(rt, g.dl(k - 1))
        path.append(('A', rt, start, -at))
        path.append(('L', corner(g, k, 'TM'), corner(g, k, 'BM')))
        path.append(('A', rb, -ab, ab))
        if k < N - 1:
            path.append(('L', corner(g, k, 'BP'), g.pt(g.r2 - g.d(k + 1), dl)))
    bp_last = corner(g, N - 1, 'BP')
    bp_n = corner(g, N, 'BP')
    r = rv[j]
    a, dl = r * g.cos, g.dl(N)
    q = (a * g.cos + dl * g.sin, a * g.sin - dl * g.cos)
    path += [('L', bp_last, bp_n), ('L', bp_n, q), ('L', q, (r, 0.0))]
    return path


def coil_local(g, N):
    """Bahnen je Lage, Durchkontaktierungen und Anschlusspunkte einer Spule in Lage um +x."""
    n = g.n
    ns, par = g.ns, g.par
    rv = g.hole_vias(N)
    angs = g.row_angles()
    tp0 = corner(g, 0, 'TP')
    tm0 = corner(g, 0, 'TM')
    th_pl = g.ang(g.r_l, g.dl0)
    s0 = g.s0  # Anfang der 1. Gruppe bei parallelen Paaren (berührt die Zuleitung von Lage 1)
    layers = {}
    for j in range(n // 2):
        k = j // par  # Gruppe: Paare einer Gruppe parallel, Gruppen in Reihe
        core = spiral_in(g, N, k, rv)
        inn = []
        if k > 0:
            xa = angs[k]
            inn = [('L', polar(g.r_v, xa), polar(g.r_l, xa)), ('A', g.r_l, xa, th_pl), ('L', polar(g.r_l, th_pl), tp0)]
        elif j > 0:
            inn = [('L', s0, tp0)]
        layers[2 * j] = inn + core
        out = reverse([mirror(pr) for pr in core])
        if k == ns - 1:
            out.append(('L', tm0, polar(g.r_v, angs[0])))
        else:
            xa = angs[k + 1]
            out += [('L', tm0, polar(g.r_l, -th_pl)), ('A', g.r_l, -th_pl, xa), ('L', polar(g.r_l, xa), polar(g.r_v, xa))]
        layers[2 * j + 1] = out
    vias = [(r, 0.0) for r in rv] + [polar(g.r_v, a) for a in angs] + ([s0] if par > 1 else [])
    return layers, vias, tp0, polar(g.r_v, angs[0])


# --- ganze Platine -----------------------------------------------------------------


def build(design):
    if design.p.boards == 3:
        return build_phase(design)
    g, N = design.geo, design.turns
    n, nc = g.n, g.nc
    m = nc // 3
    lay = Layout(design)
    local, lvias, tp0, via_t = coil_local(g, N)
    # Rolle jeder Spule: Anfang/Ende an Pad oder an Verbindungsbogen
    role = {}
    for p in range(3):
        chain = [(p - 3 * k) % nc for k in range(m)]
        for k, c in enumerate(chain):
            role[c] = (p, k == 0, k == m - 1)
        for k in range(m - 1):
            c = chain[k]
            R = g.r_ring[p]
            t0 = 2 * g.phi * c - g.ang(R, g.dl_t)
            t1 = 2 * g.phi * c - 6 * g.phi + g.ang(R, g.dl0)
            lay.tracks.append(Track(n - 1, [('A', R, t0, t1)], g.wr, p + 1, -1))
    for c in range(nc):
        th = 2 * g.phi * c
        p, first, last = role[c]
        net = p + 1
        for li, path in local.items():
            lay.tracks.append(Track(li, [rot_prim(pr, th) for pr in path], g.w, net, c))
        for v in lvias:
            lay.vias.append(Via(*rot(v, th), net, c))
        # Anfang: Lage 1 von außen zur Ecke TP_0
        if first:
            pad = g.pt(g.r_pad, g.dl_pad)
            a = g.pt(g.r_pad, g.dl0)
            start = [('L', pad, a), ('L', a, tp0)]
            lay.pads.append(Pad(*rot(pad, th), PHASES[p] + '1', net, c))
        else:
            a = g.pt(g.r_ring[p], g.dl0)
            start = [('L', a, tp0)]
            lay.vias.append(Via(*rot(a, th), net, c))
        l1 = next(t for t in lay.tracks if t.coil == c and t.layer == 0)
        l1.path[:0] = [rot_prim(pr, th) for pr in start]
        # Ende: von der Durchkontaktierung über der M-Ecke auf Lage 1 nach außen
        if last:
            b = mpt(g.pt(g.r_pad, g.dl_t))
            pad = mpt(g.pt(g.r_pad, g.dl_pad))
            stub = [('L', via_t, b), ('L', b, pad)]
            lay.pads.append(Pad(*rot(pad, th), PHASES[p] + '2', net, c))
        else:
            b = mpt(g.pt(g.r_ring[p], g.dl_t))
            stub = [('L', via_t, b)]
            lay.vias.append(Via(*rot(b, th), net, c))
        lay.tracks.append(Track(0, [rot_prim(pr, th) for pr in stub], g.w, net, c))
    return lay


def build_phase(design):
    """Eine Platine je Phase: alle Spulen in Reihe, benachbarte gegensinnig (Spulenweite = Polteilung).

    Kette 0 → nc-1 → nc-2 → … → 1: Spule 0 vorwärts (Anfang A an Pad P1), danach abwechselnd rückwärts/vorwärts.
    Ende–Ende-Verbindungen (B) auf dem inneren Ring, Anfang–Anfang (A) auf dem äußeren, beide auf der Unterseite.
    Spule 1 endet rückwärts an ihrem Anfang → Pad P2."""
    g, N = design.geo, design.turns
    n, nc = g.n, g.nc
    if nc % 2:
        raise ValueError('Je Phase eine Platine braucht eine gerade Spulenzahl.')
    lay = Layout(design, nets=('P',))
    local, lvias, tp0, via_t = coil_local(g, N)
    r_b, r_a = g.r_ring[0], g.r_ring[-1]
    for c in range(0, nc, 2):  # Ende von c ↔ Ende von c-1
        t0 = 2 * g.phi * (c - 1) - g.ang(r_b, g.dl_t)
        t1 = 2 * g.phi * c - g.ang(r_b, g.dl_t)
        lay.tracks.append(Track(n - 1, [('A', r_b, t0, t1)], g.wr, 1, -1))
    for c in range(3, nc, 2):  # Anfang von c ↔ Anfang von c-1
        t0 = 2 * g.phi * (c - 1) + g.ang(r_a, g.dl0)
        t1 = 2 * g.phi * c + g.ang(r_a, g.dl0)
        lay.tracks.append(Track(n - 1, [('A', r_a, t0, t1)], g.wr, 1, -1))
    for c in range(nc):
        th = 2 * g.phi * c
        for li, path in local.items():
            lay.tracks.append(Track(li, [rot_prim(pr, th) for pr in path], g.w, 1, c))
        for v in lvias:
            lay.vias.append(Via(*rot(v, th), 1, c))
        if c in (0, 1):  # Anschluss außen am Anfang
            pad = g.pt(g.r_pad, g.dl_pad)
            a = g.pt(g.r_pad, g.dl0)
            start = [('L', pad, a), ('L', a, tp0)]
            lay.pads.append(Pad(*rot(pad, th), 'P1' if c == 0 else 'P2', 1, c))
        else:
            a = g.pt(r_a, g.dl0)
            start = [('L', a, tp0)]
            lay.vias.append(Via(*rot(a, th), 1, c))
        l1 = next(t for t in lay.tracks if t.coil == c and t.layer == 0)
        l1.path[:0] = [rot_prim(pr, th) for pr in start]
        b = mpt(g.pt(r_b, g.dl_t))
        lay.tracks.append(Track(0, [rot_prim(('L', via_t, b), th)], g.w, 1, c))
        lay.vias.append(Via(*rot(b, th), 1, c))
    return lay


def phase_resistance(lay, rho, thickness):
    """Genauer Phasenwiderstand (20 °C) aus den Bahnlängen."""
    r = [0.0] * len(lay.nets)
    for t in lay.tracks:
        r[t.net - 1] += rho * path_length(t.path) / (t.width * thickness[t.layer]) * 1e3
    return r
