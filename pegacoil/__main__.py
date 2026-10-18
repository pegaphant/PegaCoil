"""Ohne Fusion: python -m pegacoil --od 60 --id 10 --power 10 --volt 12 --out stator.kicad_pcb"""

import argparse
import time

from . import kicad, run
from .design import Params


def main():
    ap = argparse.ArgumentParser(prog='pegacoil')
    ap.add_argument('--od', type=float, default=60, help='Außendurchmesser mm')
    ap.add_argument('--id', type=float, default=10, help='Innendurchmesser mm')
    ap.add_argument('--power', type=float, default=10, help='Leistung W')
    ap.add_argument('--volt', type=float, default=12, help='Spannung V')
    ap.add_argument('--layers', type=int, default=0, help='Lagen (0 = automatisch)')
    ap.add_argument('--coils', type=int, default=0, help='Spulen (0 = automatisch)')
    ap.add_argument('--oz', type=float, default=0, help='Kupfer außen in oz (0 = automatisch)')
    ap.add_argument('--inner-oz', type=float, default=0.5)
    ap.add_argument('--b', type=float, default=0.3, help='Flussdichte im Luftspalt T')
    ap.add_argument('--out', help='KiCad-Datei schreiben')
    a = ap.parse_args()
    p = Params(a.od, a.id, a.power, a.volt, a.layers, a.coils, a.oz, a.inner_oz, a.b)
    t = time.time()
    d, lay, text, errors = run(p)
    print(text)
    print(f'\n({time.time() - t:.1f} s)')
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(kicad.to_kicad(lay))
        print('geschrieben:', a.out)


main()
