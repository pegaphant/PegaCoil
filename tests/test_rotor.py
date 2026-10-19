"""Rotor-Stapel: Scheiben, Magnete, Höhen, Magnetisierung (ohne Fusion)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pegacoil import Params, run  # noqa: E402
from pegacoil.rotor import BACKING, IRON_T, stack  # noqa: E402


class Rotor(unittest.TestCase):
    def test_halbach_three_boards(self):
        d, *_ = run(Params(boards=3, coils=8, layers=2, outer_oz=2.0))
        st = stack(d)
        self.assertEqual(len(st.discs), 4)
        self.assertEqual(len(st.stators), 3)
        seg = d.poles * 2  # 2 Segmente je Pol
        self.assertEqual([len(x.magnets) for x in st.discs], [seg, 2 * seg, 2 * seg, seg])  # innen zwei Lagen
        self.assertEqual(st.magnet_count, 6 * seg)
        self.assertEqual([round(s.angle, 6) for s in st.stators], [0, 30, 60])  # 240° / 8 Spulen
        p = d.p
        for disc, stator in zip(st.discs, st.stators):  # Luft zwischen Scheibe und Platine
            self.assertAlmostEqual(stator.z0 - disc.z1, p.clearance)
        self.assertAlmostEqual(st.discs[0].z1, BACKING + p.magnet_h)
        self.assertAlmostEqual(st.discs[1].z1 - st.discs[1].z0, 2 * p.magnet_h)

    def test_halbach_faces_add_up(self):
        """Axiale Segmente oben/unten gleich, tangentiale gegensinnig."""
        d, *_ = run(Params(boards=1, coils=12, layers=2, outer_oz=2.0))
        bottom, top = stack(d).discs
        for mb, mt in zip(bottom.magnets, top.magnets):
            self.assertAlmostEqual(mb.a0, mt.a0)
            if 'axial' in mb.label:
                self.assertEqual(mb.label, mt.label)
            else:
                self.assertNotEqual(mb.label, mt.label)

    def test_iron(self):
        d, *_ = run(Params(boards=3, coils=8, layers=2, outer_oz=2.0, rotor='iron'))
        st = stack(d)
        self.assertEqual([len(x.magnets) for x in st.discs], [d.poles] * 4)
        self.assertIsNotNone(st.discs[0].iron)
        self.assertIsNotNone(st.discs[-1].iron)
        self.assertIsNone(st.discs[1].iron)
        self.assertAlmostEqual(st.discs[0].iron[1] - st.discs[0].iron[0], IRON_T)
        labels = [m.label for m in st.discs[0].magnets]
        self.assertEqual(labels[:2], ['N oben', 'S oben'])
        for disc in st.discs:  # alle Lagen im gleichen Muster
            self.assertEqual([m.label for m in disc.magnets], labels)

    def test_magnets_inside_disc(self):
        d, *_ = run(Params())
        st = stack(d)
        for disc in st.discs:
            self.assertLess(st.r_mag[1], disc.r_out)
            self.assertLess(disc.r_in, st.r_mag[0])
            for m in disc.magnets:
                self.assertTrue(disc.z0 - 1e-9 <= m.z0 < m.z1 <= disc.z1 + 1e-9)
                self.assertLess(m.a0, m.a1)


if __name__ == '__main__':
    unittest.main()
