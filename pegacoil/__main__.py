"""Ohne Fusion: python -m pegacoil --od 60 --id 10 --volt 12 --out stator.kicad_pcb"""

import argparse
import time

from . import kicad, run
from .design import Params


def main():
    ap = argparse.ArgumentParser(prog='pegacoil')
    ap.add_argument('--od', type=float, default=60, help='Außendurchmesser mm')
    ap.add_argument('--id', type=float, default=10, help='Innendurchmesser mm')
    ap.add_argument('--power', type=float, default=0, help='Leistung W (0 = maximal möglich)')
    ap.add_argument('--volt', type=float, default=12, help='Spannung V')
    ap.add_argument('--layers', type=int, default=0, help='Lagen (0 = automatisch)')
    ap.add_argument('--coils', type=int, default=0, help='Spulen (0 = automatisch)')
    ap.add_argument('--oz', type=float, default=0, help='Kupfer außen in oz (0 = automatisch)')
    ap.add_argument('--inner-oz', type=float, default=0, help='Kupfer innen in oz (0 = automatisch)')
    ap.add_argument('--b', type=float, default=0, help='mittlere Flussdichte T (0 = aus den Magneten)')
    ap.add_argument('--boards', type=int, default=3, choices=(1, 3), help='3 = je Phase eine Platine')
    ap.add_argument('--rotor', default='halbach', choices=('halbach', 'iron'))
    ap.add_argument('--magnet', default='N52')
    ap.add_argument('--hm', type=float, default=5.0, help='Magnetdicke mm')
    ap.add_argument('--rpm', type=float, default=10000, help='höchste Leerlaufdrehzahl (ohne Nenndrehzahl)')
    ap.add_argument('--speed', type=float, default=1500, help='Nenndrehzahl U/min (0 = höchste Leistung)')
    ap.add_argument('--h', type=float, default=12, help='Wärmeübergang W/m²K (Kühlung)')
    ap.add_argument('--out', help='KiCad-Datei schreiben')
    a = ap.parse_args()
    p = Params(a.od, a.id, a.power, a.volt, a.layers, a.coils, a.oz, a.inner_oz, a.b, max_rpm=a.rpm,
               boards=a.boards, rotor=a.rotor, magnet=a.magnet, magnet_h=a.hm,
               speed=a.speed, h_air=a.h)
    t = time.time()
    d, lay, text, errors = run(p)
    print(text)
    print(f'\n({time.time() - t:.1f} s)')
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(kicad.to_kicad(lay))
        print('geschrieben:', a.out)


main()
