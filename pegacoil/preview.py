"""Vorschau als SVG (Lagen farbig übereinander, Ansicht von oben)."""

import math

from .layout import ends

COLORS = ['#c83737', '#3771c8', '#37a837', '#c8a037', '#a037c8', '#37c8c8', '#c86437', '#646464']


def to_svg(layout, layers=None, size=900):
    d = layout.design
    g, p = d.geo, d.p
    R = p.outer_d / 2 + 1
    k = size / (2 * R)

    def P(pt):
        return f'{(pt[0] + R) * k:.2f},{(R - pt[1]) * k:.2f}'

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">',
           f'<rect width="{size}" height="{size}" fill="#10261a"/>']
    for r in (p.outer_d / 2, p.inner_d / 2):
        out.append(f'<circle cx="{R * k:.2f}" cy="{R * k:.2f}" r="{r * k:.2f}" fill="none" stroke="#ddd" stroke-width="1"/>')
    show = range(g.n) if layers is None else layers
    for li in reversed(list(show)):
        col = COLORS[li % len(COLORS)]
        for t in layout.tracks:
            if t.layer != li:
                continue
            dd = []
            for pr in t.path:
                a, b = ends(pr)
                if not dd:
                    dd.append('M' + P(a))
                if pr[0] == 'L':
                    dd.append('L' + P(b))
                else:
                    r, t0, t1 = pr[1], pr[2], pr[3]
                    large = 1 if abs(t1 - t0) > math.pi else 0
                    sweep = 0 if t1 > t0 else 1
                    dd.append(f'A{r * k:.2f},{r * k:.2f} 0 {large} {sweep} ' + P(b))
            out.append(f'<path d="{" ".join(dd)}" fill="none" stroke="{col}" stroke-opacity="0.85" '
                       f'stroke-width="{t.width * k:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    for v in layout.vias:
        out.append(f'<circle cx="{(v.x + R) * k:.2f}" cy="{(R - v.y) * k:.2f}" r="{g.vr * k:.2f}" fill="#e0c060"/>')
    for pad in layout.pads:
        x, y = (pad.x + R) * k, (R - pad.y) * k
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{g.pad_r * k:.2f}" fill="#e0c060"/>')
        out.append(f'<text x="{x:.2f}" y="{y + 4:.2f}" font-size="11" text-anchor="middle" fill="#000">{pad.name}</text>')
    out.append('</svg>')
    return '\n'.join(out)
