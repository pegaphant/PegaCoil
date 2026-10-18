"""python -m unittest discover tests  (ohne Fusion)"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pegacoil import Params, drc, kicad, layout, run  # noqa: E402
from pegacoil.design import Geo, best_for, rules  # noqa: E402

CASES = [
    dict(),
    dict(outer_d=80, inner_d=20, power_w=20, voltage_v=24),
    dict(outer_d=40, inner_d=5, power_w=3, voltage_v=5),
    dict(outer_d=100, inner_d=30, power_w=50, voltage_v=48, layers=4),
    dict(outer_d=60, inner_d=10, power_w=10, voltage_v=12, layers=2, coils=6),
    dict(outer_d=60, inner_d=10, power_w=10, voltage_v=12, layers=8, outer_oz=2.0),
    dict(outer_d=50, inner_d=8, power_w=5, voltage_v=12, coils=3, layers=2),
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
        base = dict(outer_d=60, inner_d=10, power_w=10, voltage_v=12, coils=12)
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
