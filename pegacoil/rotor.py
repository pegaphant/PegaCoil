"""Rotor und Stapel als Bauteilliste (ohne Fusion) – Grundlage für das 3D-Modell und die Magnetzählung.

Aufbau von unten nach oben (z in mm, z = 0 = Unterseite der untersten Scheibe):
  Scheibe 0 | Luft | Platine 1 | Luft | Scheibe 1 | … | Platine n | Luft | Scheibe n
Jede Platine sitzt in einem eigenen Luftspalt mit Magneten auf beiden Seiten.

Halbach: eine Lage (Dicke hm) ist nur auf einer Seite stark. Außenscheiben tragen eine Lage auf einem
unmagnetischen Träger, innere Scheiben zwei Lagen Rücken an Rücken (je eine für den Spalt darunter und darüber).
Damit sich beide Seiten im Spalt addieren, zeigen die axialen Segmente oben und unten gleich, die tangentialen
gegensinnig: stark nach oben ↑ → ↓ ←, stark nach unten ↑ ← ↓ →.
Stahlrückschluss: Außenscheiben = Stahlplatte + Magnete, innere Scheiben = Magnete durchgehend (axial, dienen
beiden Spalten). Alle Lagen N/S im selben Muster.
"""

import math
from dataclasses import dataclass, field

from .design import HALBACH_SEGMENTS

BACKING = 2.0  # mm unmagnetischer Boden unter einer Halbach-Lage (Außenscheibe)
IRON_T = 3.0  # mm Stahl-Rückschlussplatte
RIM = 3.0  # mm Träger außen über die Magnete hinaus
GAP = 0.2  # mm Fuge zwischen Magneten (am mittleren Radius)

UP_HALBACH = ('↑ axial', '→ tangential', '↓ axial', '← tangential')  # stark nach oben
DOWN_HALBACH = ('↑ axial', '← tangential', '↓ axial', '→ tangential')  # stark nach unten


@dataclass
class Magnet:
    a0: float  # Grad
    a1: float
    z0: float
    z1: float
    label: str


@dataclass
class Disc:
    name: str
    z0: float
    z1: float
    r_out: float
    r_in: float
    magnets: list = field(default_factory=list)
    iron: tuple = None  # (z0, z1) Stahlplatte


@dataclass
class Stator:
    name: str
    z0: float
    z1: float
    angle: float  # Grad, Verdrehung beim Einbau
    r_out: float
    r_in: float


@dataclass
class Stack:
    discs: list
    stators: list
    r_mag: tuple  # (innen, außen) mm
    shaft_d: float
    height: float

    @property
    def magnet_count(self):
        return sum(len(d.magnets) for d in self.discs)


def _ring(poles, halbach, z0, z1, labels):
    """Eine Magnetlage: Segmente rund um den Umfang."""
    n = poles * HALBACH_SEGMENTS // 2 if halbach else poles
    step = 360.0 / n
    out = []
    for i in range(n):
        a0 = i * step
        out.append(Magnet(a0, a0 + step, z0, z1, labels[i % len(labels)]))
    return out


def stack(d, shaft_d=None):
    """Bauteile für Auslegung d (Rotor-Scheiben, Magnete, Statoren mit Einbauwinkel)."""
    p, g = d.p, d.geo
    boards = 3 if p.boards == 3 else 1
    halbach = p.rotor == 'halbach'
    hm, cl, bt = p.magnet_h, p.clearance, p.board_t
    r_in_mag, r_out_mag = g.r1, g.r2
    r_disc = r_out_mag + RIM
    shaft = shaft_d or max(3.0, round(p.inner_d - 2.0))
    if halbach:
        up, down = UP_HALBACH, DOWN_HALBACH
    else:
        up = down = ('N oben', 'S oben')  # gleiche Lage aller Scheiben, damit der Fluss durchgeht
    discs, stators = [], []
    z = 0.0
    for k in range(boards + 1):
        name = f'Rotorscheibe {k + 1}'
        first, last = k == 0, k == boards
        if halbach:
            if first:  # Boden, darüber eine Lage stark nach oben
                disc = Disc(name, z, z + BACKING + hm, r_disc, shaft / 2)
                disc.magnets = _ring(d.poles, True, z + BACKING, z + BACKING + hm, up)
            elif last:  # eine Lage stark nach unten, darüber Boden
                disc = Disc(name, z, z + hm + BACKING, r_disc, shaft / 2)
                disc.magnets = _ring(d.poles, True, z, z + hm, down)
            else:  # zwei Lagen Rücken an Rücken
                disc = Disc(name, z, z + 2 * hm, r_disc, shaft / 2)
                disc.magnets = (_ring(d.poles, True, z, z + hm, [x + ', untere Lage' for x in down])
                                + _ring(d.poles, True, z + hm, z + 2 * hm, [x + ', obere Lage' for x in up]))
        else:
            if first:
                disc = Disc(name, z, z + IRON_T + hm, r_disc, shaft / 2, iron=(z, z + IRON_T))
                disc.magnets = _ring(d.poles, False, z + IRON_T, z + IRON_T + hm, up)
            elif last:
                disc = Disc(name, z, z + hm + IRON_T, r_disc, shaft / 2, iron=(z + hm, z + hm + IRON_T))
                disc.magnets = _ring(d.poles, False, z, z + hm, up)
            else:
                disc = Disc(name, z, z + hm, r_disc, shaft / 2)
                disc.magnets = _ring(d.poles, False, z, z + hm, up)
        if not halbach:  # Polbedeckung: Magnete schmaler als die Polteilung
            for m in disc.magnets:
                pitch = m.a1 - m.a0
                trim = pitch * (1 - p.pole_arc) / 2
                m.a0, m.a1 = m.a0 + trim, m.a1 - trim
        discs.append(disc)
        z = disc.z1
        if not last:
            z0 = z + cl
            phase = 'UVW'[k] if boards == 3 else 'UVW'
            angle = k * 240.0 / d.coils if boards == 3 else 0.0
            stators.append(Stator(f'Stator {k + 1} ({phase})', z0, z0 + bt, angle, p.outer_d / 2, p.inner_d / 2))
            z = z0 + bt + cl
    for disc in discs:  # Fuge zwischen den Magneten
        for m in disc.magnets:
            half = math.degrees(GAP / ((r_in_mag + r_out_mag) / 2)) / 2
            m.a0, m.a1 = m.a0 + half, m.a1 - half
    return Stack(discs, stators, (r_in_mag, r_out_mag), shaft, z)
