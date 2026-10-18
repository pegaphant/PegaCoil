"""Auslegung eines 3-phasigen Axialfluss-PCB-Motors (Stator als Leiterplatte).

Reines Python ohne Fusion-Abhängigkeit. Längen in mm, Winkel in Radiant.

Aufbau einer Spule (lokal, Spulenmitte auf der +x-Achse):
  Sektor zwischen den Strahlen ±phi (phi = pi / Spulenzahl), innen r1, außen r2.
  Windung k ist die um d_k = w/2 + k·(w+s) nach innen versetzte Sektorkontur.
  Lagen 1, 3, 5 … laufen im Uhrzeigersinn nach innen, Lagen 2, 4, 6 … gespiegelt wieder
  nach außen – der Strom kreist in allen Lagen gleich herum. Lagenpaare sind über
  Durchkontaktierungen in der Spulenmitte (innen) bzw. in einer Reihe über der Spule
  (außen) in Reihe geschaltet.

Wicklung: 3 Spulen : 2 Magnetpole (z. B. 12 Spulen / 8 Pole), Spulen U V W U V W …,
alle Spulen einer Phase in Reihe. Anschlüsse U1/U2, V1/V2, W1/W2 als Lötpads außen –
Stern oder Dreieck wird beim Anlöten gewählt.
"""

import math
from dataclasses import dataclass

RHO_CU = 1.72e-8  # Ohm·m bei 20 °C
ALPHA_CU = 0.00393  # 1/K
OZ_MM = 0.035  # 1 oz/ft² Kupfer ≈ 35 µm
H_AIR = 12.0  # W/(m²·K), freie Konvektion + Strahlung je Seite
KW = math.sqrt(3) / 2  # Wicklungsfaktor bei 3 Spulen : 2 Polen
EDGE_PAD = 0.5  # Pad-Kupfer bis Außenkante
VIA_AMPS = 1.0  # grobe Belastbarkeit einer 0,3-mm-Durchkontaktierung
COIL_CHOICES = (3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 36)
LAYER_CHOICES = (2, 4, 6, 8)
OZ_CHOICES = (1.0, 2.0)
PHASES = ('U', 'V', 'W')


@dataclass
class Params:
    outer_d: float = 60.0
    inner_d: float = 10.0
    power_w: float = 10.0
    voltage_v: float = 12.0
    layers: int = 0  # 0 = automatisch
    coils: int = 0  # 0 = automatisch
    outer_oz: float = 0.0  # 0 = automatisch (1 oder 2 oz)
    inner_oz: float = 0.5
    b_gap: float = 0.3  # T, Flussdichte im Luftspalt
    max_rise: float = 40.0  # K, zulässige Erwärmung der Platine
    min_trace: float = 0.0  # 0 = nach Kupferdicke
    min_space: float = 0.0
    via_drill: float = 0.3
    via_pad: float = 0.6
    pad_drill: float = 1.0
    pad_d: float = 2.0
    edge_clear: float = 0.3  # Kupfer bis Innenbohrung
    board_t: float = 1.6


def rules(p, layers, outer_oz):
    """Kleinste Bahnbreite und Abstand (Fertigerregeln wie JLCPCB, etwas vorsichtig)."""
    oz = max(outer_oz, p.inner_oz if layers > 2 else 0.0)
    auto = 0.2 if oz > 1.0 else 0.127
    return (p.min_trace or auto), (p.min_space or auto)


def layer_thickness(n, outer_oz, inner_oz):
    return [outer_oz * OZ_MM] + [inner_oz * OZ_MM] * (n - 2) + [outer_oz * OZ_MM]


def polar(r, t):
    return (r * math.cos(t), r * math.sin(t))


class Geo:
    """Geometrie einer Spule und der Anschlusszonen für feste Bahnbreite w."""

    def __init__(self, p, n, nc, w, s, r1):
        self.p, self.n, self.nc, self.w, self.s, self.r1 = p, n, nc, w, s, r1
        self.phi = math.pi / nc
        self.sin, self.cos = math.sin(self.phi), math.cos(self.phi)
        self.pitch = w + s
        self.vr = p.via_pad / 2
        self.wr = max(w, 0.4)  # Breite der Verbindungsbögen
        self.pad_r = p.pad_d / 2
        self.r_pad = p.outer_d / 2 - EDGE_PAD - self.pad_r
        vr2 = max(self.vr, self.wr / 2)
        self.ring_step = self.wr / 2 + vr2 + s
        top = self.r_pad - self.pad_r - s - vr2
        self.r_ring = [top - 2 * self.ring_step, top - self.ring_step, top]
        self.r_v = self.r_ring[0] - vr2 - s - self.vr  # Reihe der äußeren Durchkontaktierungen
        self.r_l = self.r_v - self.vr - s - w / 2  # Reihe der Übergangsleitungen
        self.r2 = self.r_l - w / 2 - s  # Kupferkante außen
        self.dl0 = s / 2 + w / 2
        self.dl_t = self.dl0 + max(0.0, self.vr - w / 2)
        self.dl_pad = self.pad_r + s / 2
        self.via_sp = self.vr + max(self.vr, w / 2) + s

    # --- Kontur k ---------------------------------------------------------
    def d(self, k):
        return self.w / 2 + k * self.pitch

    def dl(self, k):
        return self.s / 2 + self.d(k)

    def pt(self, rho, dl):
        """Punkt im Abstand rho vom Ursprung auf der um dl versetzten Linie der P-Seite (y > 0)."""
        a = math.sqrt(max(rho * rho - dl * dl, 0.0))
        return (a * self.cos + dl * self.sin, a * self.sin - dl * self.cos)

    def ang(self, rho, dl):
        x, y = self.pt(rho, dl)
        return math.atan2(y, x)

    def contour_ok(self, k):
        d, dl = self.d(k), self.dl(k)
        rt, rb = self.r2 - d, self.r1 + d
        if rb <= dl or rt <= rb:
            return False
        ab, at = math.sqrt(rb * rb - dl * dl), math.sqrt(rt * rt - dl * dl)
        yb = ab * self.sin - dl * self.cos
        return yb > 0 and at - ab > self.pitch

    def hole_vias(self, N):
        """Radien der inneren Durchkontaktierungen (oben zuerst) oder None."""
        if N < 1 or not self.contour_ok(N):
            return None
        c = self.w / 2 + self.s + self.vr
        hi = self.r2 - self.d(N - 1) - c
        lo = max(self.r1 + self.d(N - 1) + c, (self.dl(N) + c) / self.sin)
        nv = self.n // 2
        if hi - lo < (nv - 1) * self.via_sp - 1e-9:
            return None
        rv = [hi - j * self.via_sp for j in range(nv)]
        rb = self.r1 + self.d(N)
        ab = math.sqrt(rb * rb - self.dl(N) ** 2)
        if rv[-1] * self.cos <= ab + self.w:
            return None
        return rv

    def row_angles(self):
        """Winkel der äußeren Durchkontaktierungen auf r_v; [0] = Endanschluss (M-Seite)."""
        if self.r2 <= self.r1:
            return None
        t0 = -self.ang(self.r_v, self.dl_t)
        step = 2 * math.asin(min(1.0, (2 * self.vr + self.s) / (2 * self.r_v)))
        angs = [t0 + j * step for j in range(self.n // 2)]
        clear = self.vr + self.w / 2 + self.s
        limit = self.ang(self.r_v, self.dl0) - 2 * math.asin(min(1.0, clear / (2 * self.r_v)))
        if angs[-1] > limit + 1e-12:
            return None
        if self.n > 2 and angs[1] - step / 2 < -self.ang(self.r_l, self.dl0):
            return None
        return angs

    def fits(self, N):
        if self.r1 + 2 * self.w >= self.r2:
            return False
        return self.row_angles() is not None and self.contour_ok(N - 1) and self.hole_vias(N) is not None

    def coil_sums(self, N):
        """(Bahnlänge einer Lage, Hebelfläche S) für N Windungen; S = Σ (a_oben² − a_unten²)."""
        L = S = 0.0
        for k in range(N):
            d, dl = self.d(k), self.dl(k)
            rt, rb = self.r2 - d, self.r1 + d
            at, ab = math.sqrt(rt * rt - dl * dl), math.sqrt(rb * rb - dl * dl)
            L += 2 * rt * self.ang(rt, dl) + 2 * rb * self.ang(rb, dl) + 2 * (at - ab)
            S += at * at - ab * ab
        L += 0.5 * (self.r2 - self.r1) + (self.r_v - self.r2) + self.r_l * self.phi
        return L, S


@dataclass
class Design:
    p: Params
    layers: int
    coils: int
    outer_oz: float
    turns: int
    w: float
    s: float
    r1: float
    geo: Geo
    r_coil: float = 0.0  # Ohm, 20 °C
    r_phase: float = 0.0
    r_ll: float = 0.0  # zwischen zwei Anschlüssen in Sternschaltung
    current: float = 0.0
    limited: bool = False  # Treiber muss den Strom begrenzen
    kt: float = 0.0  # Nm/A
    torque: float = 0.0  # Nm
    p_cu: float = 0.0
    rise: float = 0.0
    p_cont: float = 0.0  # Dauerleistung bei max_rise

    @property
    def poles(self):
        return 2 * self.coils // 3

    @property
    def rpm0(self):
        return self.p.voltage_v / self.kt * 60 / (2 * math.pi) if self.kt > 0 else 0.0


def evaluate(geo, N, p, oz):
    n, nc = geo.n, geo.nc
    L, S = geo.coil_sums(N)
    ts = layer_thickness(n, oz, p.inner_oz)
    r_coil = sum(RHO_CU * L / (geo.w * t) * 1e3 for t in ts)
    m = nc // 3
    t_o = oz * OZ_MM
    ring_len = (m - 1) * 6 * geo.phi * geo.r_ring[1]
    stub_len = 2 * m * (geo.r_ring[1] - geo.r2) + 2 * (geo.r_pad - geo.r_ring[1])
    r_phase = m * r_coil + RHO_CU * 1e3 * (ring_len / (geo.wr * t_o) + stub_len / (geo.w * t_o))
    r_ll = 2 * r_phase
    i_t = p.power_w / p.voltage_v
    if r_ll >= p.voltage_v / i_t:
        current, limited = p.voltage_v / r_ll, False
    else:
        current, limited = i_t, True
    kt = 2 * m * KW * p.b_gap * n * S * 1e-6  # S je Lage, alle Lagen tragen
    area = math.pi * ((p.outer_d / 2) ** 2 - (p.inner_d / 2) ** 2) * 1e-6
    p_cu = current * current * r_ll
    d = Design(p, n, nc, oz, N, geo.w, geo.s, geo.r1, geo)
    d.r_coil, d.r_phase, d.r_ll = r_coil, r_phase, r_ll
    d.current, d.limited, d.kt, d.torque = current, limited, kt, kt * current
    d.p_cu, d.rise = p_cu, p_cu / (H_AIR * 2 * area)
    d.p_cont = H_AIR * 2 * area * p.max_rise
    return d


def best_for(p, n, oz, nc, r1, w_min, s):
    best, worse = None, 0
    for N in range(1, 500):
        if not Geo(p, n, nc, w_min, s, r1).fits(N):
            break
        lo, hi = w_min, w_min + 4.0
        for _ in range(14):
            mid = (lo + hi) / 2
            if Geo(p, n, nc, mid, s, r1).fits(N):
                lo = mid
            else:
                hi = mid
        w = max(w_min, math.floor(lo * 1000) / 1000)
        d = evaluate(Geo(p, n, nc, w, s, r1), N, p, oz)
        if best is None or d.torque > best.torque * (1 + 1e-9):
            best, worse = d, 0
        else:
            worse += 1
            if worse >= 3 and not d.limited:
                break
    return best


def candidates(p):
    """Beste Auslegung je Kombination aus Lagen, Kupfer und Spulenzahl."""
    out = []
    layers = (p.layers,) if p.layers else LAYER_CHOICES
    ozs = (p.outer_oz,) if p.outer_oz else OZ_CHOICES
    coils = (p.coils,) if p.coils else COIL_CHOICES
    r1_min = p.inner_d / 2 + p.edge_clear
    for n in layers:
        for oz in ozs:
            w_min, s = rules(p, n, oz)
            for nc in coils:
                g = Geo(p, n, nc, w_min, s, r1_min)
                span = g.r2 - r1_min
                if span <= 1.0:
                    continue
                best = None
                for f in (0.0, 0.12, 0.25, 0.4):
                    d = best_for(p, n, oz, nc, r1_min + f * span, w_min, s)
                    if d and (best is None or d.torque > best.torque):
                        best = d
                if best:
                    out.append(best)
    return out


def cost(d):
    return d.layers + (1.5 if d.outer_oz > 1 else 0.0)


def choose(results, share=0.8):
    """Günstigste Auslegung mit mindestens `share` des besten Drehmoments."""
    if not results:
        return None
    t_best = max(r.torque for r in results)
    ok = [r for r in results if r.torque >= share * t_best]
    return min(ok, key=lambda r: (cost(r), -r.torque))


def optimize(p):
    """(gewählte Auslegung, alle Kandidaten). Wirft ValueError bei unmöglichen Vorgaben."""
    if p.outer_d <= p.inner_d + 10:
        raise ValueError('Außendurchmesser muss mindestens 10 mm größer sein als der Innendurchmesser.')
    if p.power_w <= 0 or p.voltage_v <= 0:
        raise ValueError('Leistung und Spannung müssen größer als 0 sein.')
    results = candidates(p)
    best = choose(results)
    if best is None:
        raise ValueError('Keine Spule passt auf die Ringfläche – Platine größer oder Innendurchmesser kleiner wählen.')
    return best, results
