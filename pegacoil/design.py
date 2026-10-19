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

import copy
import math
from dataclasses import dataclass, replace

RHO_CU = 1.72e-8  # Ohm·m bei 20 °C
ALPHA_CU = 0.00393  # 1/K
OZ_MM = 0.035  # 1 oz/ft² Kupfer ≈ 35 µm
H_AIR = 12.0  # W/(m²·K), freie Konvektion + Strahlung je Seite
KW = math.sqrt(3) / 2  # Wicklungsfaktor bei 3 Spulen : 2 Polen
EDGE_PAD = 0.5  # Pad-Kupfer bis Außenkante
VIA_AMPS = 1.0  # grobe Belastbarkeit einer 0,3-mm-Durchkontaktierung
COIL_CHOICES = (3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 36)  # 1 Platine, 3 Phasen (3 Spulen : 2 Pole)
PHASE_COIL_CHOICES = (6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36)  # je Phase eine Platine (1 Spule je Pol)
LAYER_CHOICES = (2, 4, 6, 8, 10, 12)
MAGNETS = {'N35': 1.19, 'N42': 1.30, 'N45': 1.35, 'N48': 1.40, 'N52': 1.45}  # Remanenz Br in T
HALBACH_SEGMENTS = 4  # Segmente je Wellenlänge (2 je Pol)
HALBACH_QUALITY = 0.85  # echte Ringe: Fugen, Magnetisierungsfehler (ideale Formel ist zu optimistisch)
OZ_CHOICES = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 13.0)  # PCBWay: Heavy Copper bis 13 oz
INNER_OZ_CHOICES = (0.5, 1.0, 2.0, 3.0, 4.0, 6.0)
# Kleinste Bahnbreite/Abstand je Kupferdicke (vorsichtig; Heavy Copper braucht deutlich mehr Abstand).
# Vor der Bestellung mit den aktuellen Fertigerregeln vergleichen – überschreibbar über min_trace/min_space.
COPPER_RULES = ((1.0, 0.127), (2.0, 0.2), (3.0, 0.25), (4.0, 0.3), (6.0, 0.4), (8.0, 0.5), (10.0, 0.6), (13.0, 0.75))
DIELECTRIC = 0.2  # mm Mindest-Isolierung zwischen zwei Kupferlagen
PHASES = ('U', 'V', 'W')


@dataclass
class Params:
    outer_d: float = 60.0
    inner_d: float = 10.0
    power_w: float = 0.0  # W mechanische Dauerleistung, 0 = so viel, wie die Platine dauerhaft schafft
    voltage_v: float = 12.0
    layers: int = 0  # 0 = automatisch
    coils: int = 0  # 0 = automatisch
    outer_oz: float = 0.0  # 0 = automatisch (bis 13 oz)
    inner_oz: float = 0.0  # 0 = automatisch (wie außen, bis 6 oz)
    b_gap: float = 0.0  # T, mittlere Flussdichte im Luftspalt; 0 = aus den Magneten berechnet
    max_rise: float = 40.0  # K, zulässige Erwärmung der Platine
    max_rpm: float = 10000.0  # U/min, höchste Leerlaufdrehzahl (sonst nur Watt durch Drehzahl)
    min_trace: float = 0.0  # 0 = nach Kupferdicke
    min_space: float = 0.0
    via_drill: float = 0.3
    via_pad: float = 0.6
    pad_drill: float = 1.0
    pad_d: float = 2.0
    edge_clear: float = 0.3  # Kupfer bis Innenbohrung
    board_t: float = 1.6
    boards: int = 3  # 3 = je Phase eine Platine (gestapelt), 1 = eine Platine mit allen 3 Phasen
    rotor: str = 'halbach'  # 'halbach' (beidseitig, ohne Eisen) oder 'iron' (beidseitig auf Stahlrückschluss)
    magnet: str = 'N52'
    magnet_h: float = 5.0  # mm Magnetdicke je Seite
    clearance: float = 0.5  # mm Luft je Seite zwischen Platine und Magnet
    pole_arc: float = 0.8  # Polbedeckung (nur Rückschluss; Halbach füllt den Umfang)


def flux(p, poles, r_m, board_t):
    """(B1, B_mittel) im Luftspalt in T: Grundwelle an der Platinenmitte bei Magneten auf beiden Seiten und
    die mittlere Flussdichte unter einem Leiter (2/π · B1), mit der das Drehmoment gerechnet wird.
    Polteilung τ am mittleren Spulenradius – mehr Pole = kürzere Polteilung = mehr Streufeld."""
    if p.b_gap > 0:
        return p.b_gap * math.pi / 2, p.b_gap
    br = MAGNETS.get(p.magnet, 1.3)
    tau = 2 * math.pi * r_m / poles
    k = math.pi / tau
    g = board_t + 2 * p.clearance  # Abstand der Magnetflächen
    hm = p.magnet_h
    if p.rotor == 'halbach':
        m = HALBACH_SEGMENTS
        seg = math.sin(math.pi / m) / (math.pi / m)
        b1 = HALBACH_QUALITY * 2 * br * seg * (1 - math.exp(-k * hm)) * math.exp(-k * g / 2)
    else:
        b1 = 4 / math.pi * br * math.sin(p.pole_arc * math.pi / 2) * math.sinh(k * hm) / math.sinh(k * (hm + g / 2))
    return b1, 2 / math.pi * b1


def rules(p, layers, outer_oz):
    """Kleinste Bahnbreite und Abstand – alle Lagen haben dasselbe Muster, die dickste Lage bestimmt."""
    oz = max(outer_oz, p.inner_oz if layers > 2 else 0.0)
    auto = next(v for o, v in COPPER_RULES if oz <= o + 1e-9) if oz <= COPPER_RULES[-1][0] else COPPER_RULES[-1][1]
    return (p.min_trace or auto), (p.min_space or auto)


def board_thickness(p, layers, outer_oz):
    """Platinendicke: Vorgabe, aber mindestens Kupfer + Isolierung zwischen den Lagen."""
    cu = sum(layer_thickness(layers, outer_oz, p.inner_oz))
    return max(p.board_t, round(cu + (layers - 1) * DIELECTRIC + 0.05, 1))


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
        self.vh = max(self.vr, w / 2)  # Kupfer um eine Durchkontaktierung (Bahnende ist breiter als das Pad)
        self.wr = max(w, 0.4)  # Breite der Verbindungsbögen
        self.pad_r = p.pad_d / 2
        self.pad_h = max(self.pad_r, w / 2)  # Kupfer am Pad (breite Bahn ragt über das Pad)
        self.r_pad = p.outer_d / 2 - EDGE_PAD - self.pad_h
        vr2 = max(self.vr, self.wr / 2)
        self.ring_step = self.wr / 2 + vr2 + s
        top = self.r_pad - self.pad_h - s - vr2
        # Verbindungsbögen: 3 Ringe (U, V, W) bzw. bei einer Phase je Platine 2 (Ende–Ende, Anfang–Anfang)
        nr = 2 if p.boards == 3 else 3
        self.r_ring = [top - (nr - 1 - i) * self.ring_step for i in range(nr)]
        self.r_v = self.r_ring[0] - vr2 - s - self.vh  # Reihe der äußeren Durchkontaktierungen
        self.r_l = self.r_v - self.vh - s - w / 2  # Reihe der Übergangsleitungen
        self.r2 = self.r_l - w / 2 - s  # Kupferkante außen
        self.dl0 = s / 2 + w / 2
        self.dl_t = self.dl0 + max(0.0, self.vr - w / 2)
        self.dl_pad = self.pad_h + s / 2
        # Der Zug zur Durchkontaktierung j steht senkrecht auf der Spulenflanke und passiert j + 1 im
        # Abstand via_sp · cos(phi).
        self.via_sp = max(2 * self.vh + s, (self.vr + w / 2 + s) / self.cos)

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
        c = self.w / 2 + self.s + self.vh
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
        step = 2 * math.asin(min(1.0, (2 * self.vh + self.s) / (2 * self.r_v)))
        angs = [t0 + j * step for j in range(self.n // 2)]
        clear = self.vh + self.w / 2 + self.s
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
    p_cont: float = 0.0  # zulässige Kupferverluste bei max_rise
    i_max: float = 0.0  # A, höchster Dauerstrom (Erwärmung bzw. U/R)
    r_hot: float = 0.0  # Ohm zwischen zwei Anschlüssen, warm (+max_rise)
    p_max: float = 0.0  # W, höchste mechanische Dauerleistung dieser Auslegung
    p_mech: float = 0.0  # W, mechanische Leistung im Betriebspunkt (Drehmoment × Drehzahl)
    capped: bool = False  # gewünschte Leistung passt nicht → auf p_max begrenzt
    p_top: float = 0.0  # W, höchste mechanische Dauerleistung aller Auslegungen dieser Größe
    p_wanted: float = 0.0  # W, Vorgabe (0 = automatisch)
    b1: float = 0.0  # T, Grundwelle im Luftspalt
    b: float = 0.0  # T, mittlere Flussdichte unter den Leitern

    @property
    def usable(self):
        """Schafft die Vorgabe dauerhaft und dreht nicht unsinnig schnell."""
        return not self.capped and self.rpm0 <= self.p.max_rpm

    @property
    def p_in(self):
        return self.p.voltage_v * self.current

    @property
    def rpm(self):
        """Drehzahl im Betriebspunkt (Dauerstrom)."""
        return max(0.0, self.p.voltage_v - self.current * self.r_hot) / self.kt * 60 / (2 * math.pi) if self.kt > 0 else 0.0

    @property
    def poles(self):
        return self.coils if self.p.boards == 3 else 2 * self.coils // 3

    @property
    def rpm0(self):
        return self.p.voltage_v / self.kt * 60 / (2 * math.pi) if self.kt > 0 else 0.0


def evaluate(geo, N, p, oz):
    n, nc = geo.n, geo.nc
    L, S = geo.coil_sums(N)
    ts = layer_thickness(n, oz, p.inner_oz)
    r_coil = sum(RHO_CU * L / (geo.w * t) * 1e3 for t in ts)
    t_o = oz * OZ_MM
    if p.boards == 3:
        # je Phase eine Platine: alle Spulen in Reihe, benachbarte gegensinnig, Spulenweite = Polteilung
        m, kw, poles = nc, 1.0, nc
        r_mid = sum(geo.r_ring) / len(geo.r_ring)
        ring_len = (nc - 1) * 2 * geo.phi * r_mid
        stub_len = 2 * nc * (geo.r_ring[-1] - geo.r2) + 2 * (geo.r_pad - geo.r2)
    else:
        m, kw, poles = nc // 3, KW, 2 * nc // 3
        ring_len = (m - 1) * 6 * geo.phi * geo.r_ring[1]
        stub_len = 2 * m * (geo.r_ring[1] - geo.r2) + 2 * (geo.r_pad - geo.r_ring[1])
    r_phase = m * r_coil + RHO_CU * 1e3 * (ring_len / (geo.wr * t_o) + stub_len / (geo.w * t_o))
    r_ll = 2 * r_phase
    b1, b = flux(p, poles, (geo.r1 + geo.r2) / 2, p.board_t)
    kt = 2 * m * kw * b * n * S * 1e-6  # S je Lage, alle Lagen tragen
    area = math.pi * ((p.outer_d / 2) ** 2 - (p.inner_d / 2) ** 2) * 1e-6
    p_cont = H_AIR * 2 * area * p.max_rise * max(1, p.boards)  # jede Platine kühlt über beide Seiten
    # Dauerstrom: Kupferverlust (warm) höchstens p_cont, und nie mehr als U/R im Stillstand.
    # Mechanische Leistung P = I · (U − I · R_warm) (Gegenspannung = Rest der Spannung), größte bei I = U / 2R.
    v = p.voltage_v
    r_hot = r_ll * (1 + ALPHA_CU * p.max_rise)
    i_max = min(math.sqrt(p_cont / r_hot), v / r_ll)
    i_pk = min(i_max, v / (2 * r_hot))
    p_max = i_pk * (v - i_pk * r_hot)
    i_need = math.inf
    if p.power_w > 0 and v * v >= 4 * r_hot * p.power_w:
        i_need = (v - math.sqrt(v * v - 4 * r_hot * p.power_w)) / (2 * r_hot)
    capped = p.power_w > 0 and i_need > i_pk * (1 + 1e-9)
    current = i_pk if p.power_w <= 0 or capped else i_need
    limited = i_max < v / r_ll * (1 - 1e-9)  # im Stillstand flösse mehr → Treiber begrenzt
    p_cu = current * current * r_hot
    d = Design(p, n, nc, oz, N, geo.w, geo.s, geo.r1, geo)
    d.r_coil, d.r_phase, d.r_ll = r_coil, r_phase, r_ll
    d.current, d.limited, d.kt, d.torque = current, limited, kt, kt * current
    d.p_cu, d.rise = p_cu, p_cu / (H_AIR * 2 * area)
    d.p_cont, d.i_max, d.r_hot, d.p_max, d.capped = p_cont, i_max, r_hot, p_max, capped
    d.p_mech = current * (v - current * r_hot)
    d.b1, d.b = b1, b
    d.rise = p_cu / (H_AIR * 2 * area * max(1, p.boards))
    return d


def _better(d, best):
    """Auslegungen, die die Vorgabe dauerhaft schaffen, zuerst; dann (automatisch) die größere Leistung bzw.
    (Vorgabe) das größere Drehmoment."""
    if best is None or d.usable != best.usable:
        return best is None or d.usable
    if d.p.power_w <= 0:  # automatisch: so viel Leistung wie möglich, bei Gleichstand mehr Drehmoment
        if abs(d.p_max - best.p_max) > 1e-6 * max(best.p_max, 1e-9):
            return d.p_max > best.p_max
    return d.torque > best.torque * (1 + 1e-9)


def best_for(p, n, oz, nc, r1, w_min, s):
    best, worse, p_top = None, 0, 0.0
    for N in range(1, 500):
        if not Geo(p, n, nc, w_min, s, r1).fits(N):
            break
        g0 = Geo(p, n, nc, w_min, s, r1)
        lo, hi = w_min, max(w_min + 4.0, g0.r2 - r1)  # bei 1 Windung kann die Bahn fast die ganze Spule füllen
        for _ in range(12):  # Spanne bis ~40 mm → 0,01 mm genau
            mid = (lo + hi) / 2
            if Geo(p, n, nc, mid, s, r1).fits(N):
                lo = mid
            else:
                hi = mid
        w = max(w_min, math.floor(lo * 1000) / 1000)
        d = evaluate(Geo(p, n, nc, w, s, r1), N, p, oz)
        if d.rpm0 <= p.max_rpm:
            p_top = max(p_top, d.p_max)
        if _better(d, best):
            best, worse = d, 0
        else:
            worse += 1
            if worse >= 3 and not d.limited:
                break
    if best:
        best.p_top = p_top
    return best


_cache = {}


def candidates(p, only=None):
    """Beste Auslegung je Kombination aus Lagen, Kupfer und Spulenzahl (zwischengespeichert – die Live-Anzeige
    fragt dieselbe Größe mehrfach). `only`: nur diese Kombinationen (Lagen, außen, innen, Spulen)."""
    key = repr(p) + repr(sorted(only) if only is not None else None)
    if key not in _cache:
        if len(_cache) > 64:
            _cache.clear()
        _cache[key] = _candidates(p, only)
    return [copy.copy(d) for d in _cache[key]]


def inner_choices(p, n, oz):
    """Innenkupfer: automatisch so dick wie außen (höchstens 6 oz) – dickeres Innenkupfer bringt immer mehr
    Leistung, die Innenlagen liegen in Reihe und führen den vollen Strom."""
    if n <= 2:
        return (INNER_OZ_CHOICES[0],)
    if p.inner_oz:
        return (p.inner_oz,)
    return (max(c for c in INNER_OZ_CHOICES if c <= max(oz, INNER_OZ_CHOICES[0])),)


def _candidates(p, only=None):
    out = []
    layers = (p.layers,) if p.layers else LAYER_CHOICES
    ozs = (p.outer_oz,) if p.outer_oz else OZ_CHOICES
    allowed = PHASE_COIL_CHOICES if p.boards == 3 else COIL_CHOICES
    coils = (p.coils,) if p.coils else allowed
    if p.coils and (p.coils % 2 if p.boards == 3 else p.coils % 3):
        raise ValueError('Spulenzahl passt nicht: je Phase eine Platine braucht eine gerade Zahl, '
                         'eine Platine mit 3 Phasen ein Vielfaches von 3.')
    r1_min = p.inner_d / 2 + p.edge_clear
    for n in layers:
        top_n, worse = 0.0, 0
        for oz in ozs:
            # Kupfer automatisch: dicker hilft, bis der größere Mindestabstand überwiegt → nach zwei schlechteren
            # Stufen aufhören
            if worse >= 2 and only is None:
                break
            start = len(out)
            for io in inner_choices(p, n, oz):
                pn = replace(p, inner_oz=io)
                pn = replace(pn, board_t=board_thickness(pn, n, oz))
                w_min, s = rules(pn, n, oz)
                for nc in coils:
                    if only is not None and (n, oz, io, nc) not in only:
                        continue
                    g = Geo(pn, n, nc, w_min, s, r1_min)
                    span = g.r2 - r1_min
                    if span <= 1.0:
                        continue
                    best = None
                    for f in (0.0, 0.15, 0.3):
                        d = best_for(pn, n, oz, nc, r1_min + f * span, w_min, s)
                        if d and _better(d, best):
                            d.p_top = max(d.p_top, best.p_top if best else 0.0)
                            best = d
                        elif d:
                            best.p_top = max(best.p_top, d.p_top)
                    if best:
                        out.append(best)
            top_oz = max((d.p_top for d in out[start:]), default=0.0)
            if top_oz > top_n:
                top_n, worse = top_oz, 0
            else:
                worse += 1
    return out


def key_of(d):
    return (d.layers, d.outer_oz, d.p.inner_oz, d.coils)


def cost(d):
    """Grobe Kosten: Lagen, Heavy Copper außen und innen."""
    inner = (d.layers - 2) * 0.3 * max(0.0, d.p.inner_oz - 0.5) if d.layers > 2 else 0.0
    return d.layers + 0.75 * max(0.0, d.outer_oz - 1.0) + inner


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
    if p.power_w < 0 or p.voltage_v <= 0:
        raise ValueError('Spannung muss größer als 0 sein, Leistung mindestens 0 (= maximal möglich).')
    # Vergleich: jede Variante bei ihrem eigenen Maximum (Leistung automatisch)
    compare = candidates(replace(p, power_w=0.0))
    if not compare:
        raise ValueError('Keine Spule passt auf die Ringfläche – Platine größer oder Innendurchmesser kleiner wählen.')
    p_top = max(r.p_top for r in compare)
    target = p.power_w if 0 < p.power_w <= p_top else p_top * 0.999  # automatisch bzw. zu viel → das Mögliche
    # nur die Varianten nachrechnen, die die Zielleistung überhaupt schaffen
    only = {key_of(r) for r in compare if r.p_top >= target * 0.999}
    results = candidates(replace(p, power_w=target), only)
    best = choose([r for r in results if r.usable] or results)
    best.p_top, best.p_wanted = p_top, p.power_w
    return best, [r for r in compare if r.usable] or compare


def top_power(p):
    """Höchste mechanische Dauerleistung (W) auf dieser Größe (0, wenn nichts passt)."""
    if p.outer_d <= p.inner_d + 10:
        return 0.0
    return max((r.p_top for r in candidates(replace(p, power_w=0.0))), default=0.0)


def size_for_power(p, target, od_max=400.0):
    """Kleinster Außendurchmesser (ganze mm), auf dem `target` W dauerhaft möglich sind.
    (Außendurchmesser, mögliche W) – passt es auch auf od_max nicht, kommt od_max zurück."""
    lo_lim = math.ceil(p.inner_d + 11)
    memo = {}
    # Suche mit Lagen und Kupfer der aktuellen besten Auslegung (sonst je Schritt die volle Suche über alle
    # Kupferdicken); am Ende wird ohnehin wieder voll ausgelegt und kann nur besser werden.
    # Lagen/Kupfer an der geschätzten Zielgröße festlegen (Leistung wächst etwa mit der Fläche).
    od_est = min(max(p.outer_d, lo_lim), od_max)
    for _ in range(3):
        top0 = top_power(replace(p, outer_d=float(od_est)))
        if top0 <= 0:
            od_est = min(od_max, od_est * 1.5)
            continue
        od_est = min(max(lo_lim, round(od_est * math.sqrt(target / top0))), od_max)
        break
    try:
        d0 = optimize(replace(p, outer_d=float(od_est), power_w=0.0))[0]
        fixed = replace(p, layers=d0.layers, outer_oz=d0.outer_oz, inner_oz=d0.p.inner_oz)
    except ValueError:
        fixed = p

    def top(od):
        if od not in memo:
            try:
                memo[od] = top_power(replace(fixed, outer_d=float(od)))
            except ValueError:
                memo[od] = 0.0
        return memo[od]

    od_max = int(od_max)
    od = int(od_est)
    if top(od) >= target:
        hi = od
        lo = lo_lim - 1
        while hi > lo_lim:
            guess = int(hi * math.sqrt(target / top(hi))) if top(hi) > 0 else hi - 1
            guess = max(lo_lim, min(hi - 1, guess))
            if top(guess) >= target:
                hi = guess
            else:
                lo = guess
                break
    else:
        lo = od
        hi = None
        while hi is None:
            v = top(lo)
            guess = int(lo * math.sqrt(target / v)) + 1 if v > 0 else int(lo * 1.5)
            guess = min(od_max, max(lo + 1, guess))
            if top(guess) >= target:
                hi = guess
            elif guess >= od_max:
                return od_max, top(od_max)
            else:
                lo = guess
    while hi - lo > 1:  # Bisektion auf 1 mm (feste Variante → schnell, liefert eine sichere Obergrenze)
        mid = (lo + hi) // 2
        if top(mid) >= target:
            hi = mid
        else:
            lo = mid
    # Mit voller Suche (alle Lagen/Kupfer) nach unten nachschärfen – die beste Variante wechselt je Größe
    full = {}

    def top_full(od):
        if od not in full:
            full[od] = top_power(replace(p, outer_d=float(od)))
        return full[od]

    lo = max(lo_lim - 1, int(hi * 0.7))
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if top_full(mid) >= target:
            hi = mid
        else:
            lo = mid
    return float(hi), max(top(hi) if hi in memo else 0.0, full.get(hi, 0.0))

