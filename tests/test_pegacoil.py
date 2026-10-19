"""python -m unittest discover tests  (ohne Fusion)"""

import math
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pegacoil import Params, drc, eagle, kicad, layout, run  # noqa: E402
from pegacoil.design import Geo, best_for, rules, size_for_power, top_power  # noqa: E402

CASES = [
    dict(),
    dict(outer_d=80, inner_d=20, power_w=20, voltage_v=24),
    dict(outer_d=40, inner_d=5, power_w=3, voltage_v=5),
    dict(outer_d=100, inner_d=30, power_w=50, voltage_v=48, layers=4),
    dict(outer_d=60, inner_d=10, power_w=10, voltage_v=12, layers=2, coils=6),
    dict(outer_d=60, inner_d=10, power_w=10, voltage_v=12, layers=8, outer_oz=2.0),
    dict(outer_d=50, inner_d=8, power_w=5, voltage_v=12, coils=3, layers=2),
    # früher Abstandsfehler: Bahn breiter als Via-Pad bzw. Anschluss-Pad, Zug an der Nachbar-Via vorbei
    dict(outer_d=60, inner_d=10, power_w=100, voltage_v=24, layers=8),
    dict(outer_d=60, inner_d=20, power_w=100, voltage_v=24, layers=4),
    dict(outer_d=40, inner_d=10, power_w=100, voltage_v=24, layers=8),
    dict(outer_d=150, inner_d=40, power_w=10, voltage_v=12, layers=2),
    dict(outer_d=150, inner_d=40, power_w=100, voltage_v=24, layers=8, max_rpm=1e6),
]


class Design(unittest.TestCase):
    def test_cases_pass_spacing_check(self):
        for c in CASES:
            with self.subTest(**c):
                d, lay, text, errors = run(Params(**c))
                self.assertEqual(errors, [])
                self.assertGreater(d.turns, 0)
                if c.get('layers'):
                    self.assertEqual(d.layers, c['layers'])
                if c.get('coils'):
                    self.assertEqual(d.coils, c['coils'])
                # alle Spulen prüfen (run prüft nur einen Ausschnitt)
                self.assertEqual(drc.check(lay), [])

    def test_auto_power(self):
        """Leistung 0 = das Meiste, was die Größe dauerhaft schafft."""
        d, *_ = run(Params(outer_d=60, inner_d=10, voltage_v=12, layers=4))
        self.assertEqual(d.layers, 4)
        self.assertGreater(d.p_mech, 0.5)
        self.assertAlmostEqual(d.p_mech, d.p_top, delta=0.01 * d.p_top)
        self.assertLess(d.p_mech, d.p_in)  # Welle < Aufnahme (Kupferverluste)
        self.assertAlmostEqual(d.p_in - d.p_mech, d.p_cu, delta=1e-6)
        self.assertLessEqual(d.rise, d.p.max_rise + 1e-6)
        self.assertLessEqual(d.rpm0, d.p.max_rpm)
        self.assertAlmostEqual(d.torque * d.rpm * 2 * math.pi / 60, d.p_mech, delta=0.001 * d.p_mech)

    def test_power_capped_to_possible(self):
        d, *_ = run(Params(outer_d=60, inner_d=10, power_w=500, voltage_v=12))
        self.assertEqual(d.p_wanted, 500)
        self.assertAlmostEqual(d.p_mech, d.p_top, delta=0.01 * d.p_top)
        self.assertLessEqual(d.rise, d.p.max_rise + 1e-6)

    def test_requested_power_is_met(self):
        d, *_ = run(Params(outer_d=60, inner_d=10, power_w=3, voltage_v=12))
        self.assertAlmostEqual(d.p_mech, 3, delta=0.01)
        self.assertFalse(d.capped)

    def test_size_for_power(self):
        p = Params(outer_d=60, inner_d=10, voltage_v=12, layers=4)
        od, top = size_for_power(p, 10)
        self.assertGreaterEqual(top, 10)
        self.assertLess(top_power(Params(outer_d=od - 1, inner_d=10, voltage_v=12, layers=4)), 10)

    def test_eagle_file(self):
        d, lay, *_ = run(Params(layers=6))
        root = ET.fromstring(eagle.to_eagle(lay).split('\n', 2)[2])
        board = root.find('drawing/board')
        wires = board.findall('signals/signal/wire')
        self.assertEqual(sorted({int(w.get('layer')) for w in wires}), [1, 2, 3, 14, 15, 16])
        self.assertEqual(len(board.findall('elements/element')), 6)
        self.assertEqual(len(board.findall('signals/signal/via')), len(lay.vias))
        c = d.p.outer_d / 2 + 5
        for w in wires:
            if w.get('curve'):  # Bögen um die Plattenmitte
                x1, y1, x2, y2 = (float(w.get(k)) - c for k in ('x1', 'y1', 'x2', 'y2'))
                self.assertAlmostEqual(math.hypot(x1, y1), math.hypot(x2, y2), delta=1e-3)
                ang = (math.degrees(math.atan2(y2, x2) - math.atan2(y1, x1)) + 180) % 360 - 180
                self.assertAlmostEqual(ang, float(w.get('curve')), delta=0.01)

    def test_collinear_segments_are_not_crossing(self):
        a, b = (29.69072798040428, 13.53551632719043), (61.7446838225578, 28.482521410548777)
        c, e = (66.7316816758508, 30.807996700741832), (62.25312678175971, 28.719612256159614)
        self.assertGreater(drc.seg_dist(a, b, c, e), 0.5)

    def test_check_finds_short(self):
        """Abstand absichtlich unterschreiten → Prüfung muss anschlagen."""
        p = Params(layers=2, coils=12, outer_oz=1.0)
        w, s = rules(p, 2, 1.0)
        d = best_for(p, 2, 1.0, 12, 6.0, w, s)
        d.geo = Geo(p, 2, 12, d.w, s * 0.5, d.r1)
        d.geo.s = s  # Prüfung mit dem echten Abstand
        lay = layout.build(d)
        self.assertNotEqual(drc.check(lay), [])

    def test_more_copper_more_torque(self):
        # Dauerbetrieb an der Wärmegrenze (Leistung automatisch): mehr Kupfer trägt mehr Strom
        base = dict(outer_d=60, inner_d=10, power_w=0, voltage_v=12, coils=12)
        t = [run(Params(layers=n, outer_oz=1.0, **base))[0].torque for n in (2, 4, 8)]
        self.assertLess(t[0], t[1])
        self.assertLess(t[1], t[2])

    def test_resistance_matches_voltage(self):
        d, lay, *_ = run(Params(power_w=10, voltage_v=12, layers=4))
        # Strom höchstens P/U (sonst Strombegrenzung), Kupferverlust nie über P
        self.assertLessEqual(d.p_cu, 10 * 1.001)

    def test_kicad_file(self):
        d, lay, *_ = run(Params(layers=4))
        txt = kicad.to_kicad(lay)
        self.assertEqual(txt.count('('), txt.count(')'))
        for name in ('"F.Cu"', '"In1.Cu"', '"In2.Cu"', '"B.Cu"', '"Edge.Cuts"', '(via ', '(arc ', 'thru_hole'):
            self.assertIn(name, txt)
        self.assertEqual(txt.count('(footprint'), 6)


if __name__ == '__main__':
    unittest.main()
