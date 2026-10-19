"""Export als KiCad-Platine (.kicad_pcb, Format KiCad 7 – öffnet auch KiCad 8/9).

KiCad: y zeigt nach unten → y wird gespiegelt, damit die Ansicht von oben gleich bleibt.
Mittelpunkt der Platine bei (100, 100) mm.
"""

import math

from .layout import ends

CX, CY = 100.0, 100.0


def layer_names(n):
    return ['F.Cu'] + [f'In{i}.Cu' for i in range(1, n - 1)] + ['B.Cu']


def _p(pt):
    return f'{CX + pt[0]:.4f} {CY - pt[1]:.4f}'


def _layers_block(n):
    ids = [0] + list(range(1, n - 1)) + [31]
    rows = [f'    ({i} "{name}" signal)' for i, name in zip(ids, layer_names(n))]
    rows += [
        '    (32 "B.Adhes" user "B.Adhesive")',
        '    (33 "F.Adhes" user "F.Adhesive")',
        '    (34 "B.Paste" user)',
        '    (35 "F.Paste" user)',
        '    (36 "B.SilkS" user "B.Silkscreen")',
        '    (37 "F.SilkS" user "F.Silkscreen")',
        '    (38 "B.Mask" user)',
        '    (39 "F.Mask" user)',
        '    (40 "Dwgs.User" user "User.Drawings")',
        '    (41 "Cmts.User" user "User.Comments")',
        '    (44 "Edge.Cuts" user)',
        '    (45 "Margin" user)',
        '    (46 "B.CrtYd" user "B.Courtyard")',
        '    (47 "F.CrtYd" user "F.Courtyard")',
        '    (48 "B.Fab" user)',
        '    (49 "F.Fab" user)',
    ]
    return '  (layers\n' + '\n'.join(rows) + '\n  )'


def to_kicad(layout, title='PegaCoil'):
    d = layout.design
    g, p = d.geo, d.p
    names = layer_names(g.n)
    out = [
        '(kicad_pcb (version 20221018) (generator pcbnew)',
        f'  (general (thickness {p.board_t}))',
        '  (paper "A4")',
        f'  (title_block (title "{title}") (comment 1 "PegaCoil: {d.coils} Spulen, {d.poles} Pole, {g.n} Lagen"))',
        _layers_block(g.n),
        '  (setup (pad_to_mask_clearance 0))',
        '  (net 0 "")',
    ]
    for i, ph in enumerate(layout.nets):
        out.append(f'  (net {i + 1} "{ph}")')
    for pad in layout.pads:
        ph = layout.nets[pad.net - 1]
        out.append(
            f'  (footprint "PegaCoil:Anschluss" (layer "F.Cu") (at {_p((pad.x, pad.y))})\n'
            f'    (attr through_hole)\n'
            f'    (fp_text reference "{pad.name}" (at 0 {-(g.pad_r + 1.0):.2f}) (layer "F.SilkS")\n'
            f'      (effects (font (size 1 1) (thickness 0.15))))\n'
            f'    (fp_text value "Anschluss" (at 0 {g.pad_r + 1.0:.2f}) (layer "F.Fab") hide\n'
            f'      (effects (font (size 1 1) (thickness 0.15))))\n'
            f'    (pad "1" thru_hole circle (at 0 0) (size {p.pad_d} {p.pad_d}) (drill {p.pad_drill})'
            f' (layers "*.Cu" "*.Mask") (net {pad.net} "{ph}"))\n'
            f'  )'
        )
    for r in (p.outer_d / 2, p.inner_d / 2):
        out.append(f'  (gr_circle (center {_p((0, 0))}) (end {_p((r, 0))}) (stroke (width 0.1) (type default)) (fill none) (layer "Edge.Cuts"))')
    for t in layout.tracks:
        ln = names[t.layer]
        for pr in t.path:
            a, b = ends(pr)
            if pr[0] == 'L':
                if math.dist(a, b) < 1e-4:
                    continue
                out.append(f'  (segment (start {_p(a)}) (end {_p(b)}) (width {t.width:.4f}) (layer "{ln}") (net {t.net}))')
            else:
                r, t0, t1 = pr[1], pr[2], pr[3]
                if abs(t1 - t0) * r < 1e-4:
                    continue
                tm = (t0 + t1) / 2
                mid = (r * math.cos(tm), r * math.sin(tm))
                out.append(
                    f'  (arc (start {_p(a)}) (mid {_p(mid)}) (end {_p(b)}) (width {t.width:.4f}) (layer "{ln}") (net {t.net}))'
                )
    for v in layout.vias:
        out.append(f'  (via (at {_p((v.x, v.y))}) (size {p.via_pad}) (drill {p.via_drill}) (layers "F.Cu" "B.Cu") (net {v.net}))')
    out.append(')')
    return '\n'.join(out) + '\n'
