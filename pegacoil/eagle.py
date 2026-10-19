"""Export als EAGLE-Platine (.brd, XML) – öffnet Fusion Electronics direkt als PCB-Design.

EAGLE-Lagen: 1 = Top, 16 = Bottom, Innenlagen 2, 3, … von oben und …, 14, 15 von unten.
Bögen sind Wires mit `curve` (Grad, positiv = gegen den Uhrzeigersinn). Mittelpunkt der Platine bei (C, C)
mit C = Außenradius + 5 mm, damit alles im positiven Bereich liegt.
"""

import math
from xml.sax.saxutils import quoteattr

from .design import PHASES
from .layout import ends

LAYER_NAMES = {1: 'Top', 16: 'Bottom', 17: 'Pads', 18: 'Vias', 19: 'Unrouted', 20: 'Dimension', 21: 'tPlace',
               22: 'bPlace', 25: 'tNames', 26: 'bNames', 27: 'tValues', 28: 'bValues', 29: 'tStop', 30: 'bStop',
               31: 'tCream', 32: 'bCream', 44: 'Drills', 45: 'Holes', 51: 'tDocu', 52: 'bDocu'}


def copper_layers(n):
    """EAGLE-Lagennummern für Lage 0 … n-1 (oben → unten)."""
    half = n // 2
    return list(range(1, half + 1)) + list(range(17 - half, 17))


def layer_setup(n):
    """Lagenaufbau: Kerne (*) aus je zwei Lagen, verbunden über Prepreg (+), Durchkontaktierungen 1-16."""
    ls = copper_layers(n)
    return '(' + '+'.join(f'{a}*{b}' for a, b in zip(ls[::2], ls[1::2])) + ')'


def _f(x):
    return f'{x:.4f}'.rstrip('0').rstrip('.')


def _arc_pieces(r, t0, t1, max_step=math.pi / 2):
    k = max(1, math.ceil(abs(t1 - t0) / max_step - 1e-9))
    return [(t0 + (t1 - t0) * i / k, t0 + (t1 - t0) * (i + 1) / k) for i in range(k)]


def to_eagle(layout, title='PegaCoil'):
    d = layout.design
    g, p = d.geo, d.p
    c = p.outer_d / 2 + 5.0
    cl = copper_layers(g.n)

    def wire(a, b, width, layer, curve=None):
        s = (f'<wire x1="{_f(c + a[0])}" y1="{_f(c + a[1])}" x2="{_f(c + b[0])}" y2="{_f(c + b[1])}"'
             f' width="{_f(width)}" layer="{layer}"')
        if curve:
            s += f' curve="{curve:.6f}"'
        return s + '/>'

    layers = sorted(set(cl) | set(LAYER_NAMES))
    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!DOCTYPE eagle SYSTEM "eagle.dtd">',
        '<eagle version="9.6.2">',
        '<drawing>',
        '<settings><setting alwaysvectorfont="no"/><setting verticaltext="up"/></settings>',
        '<grid distance="0.1" unitdist="mm" unit="mm" style="lines" multiple="1" display="no"'
        ' altdistance="0.01" altunitdist="mm" altunit="mm"/>',
        '<layers>',
    ]
    for n in layers:
        name = LAYER_NAMES.get(n) or f'Route{n}'
        out.append(f'<layer number="{n}" name="{name}" color="{4 if n == 1 else 1 if n == 16 else 7}" fill="1"'
                   f' visible="yes" active="yes"/>')
    out += ['</layers>', '<board>', '<plain>']
    for r in (p.outer_d / 2, p.inner_d / 2):
        out.append(f'<circle x="{_f(c)}" y="{_f(c)}" radius="{_f(r)}" width="0.1" layer="20"/>')
    out.append(f'<text x="{_f(c)}" y="{_f(c - p.inner_d / 2 - 3)}" size="1.27" layer="51" align="center">'
               f'{title} {d.coils}S{d.poles}P {g.n}L</text>')
    out += [
        '</plain>',
        '<libraries><library name="pegacoil"><packages>',
        '<package name="ANSCHLUSS">',
        f'<pad name="1" x="0" y="0" drill="{_f(p.pad_drill)}" diameter="{_f(p.pad_d)}" shape="round"/>',
        '</package>',
        '</packages></library></libraries>',
        '<attributes/><variantdefs/>',
        '<classes><class number="0" name="default" width="0" drill="0"></class></classes>',
        '<designrules name="PegaCoil">',
        f'<param name="layerSetup" value="{layer_setup(g.n)}"/>',
        f'<param name="mdWireWire" value="{_f(g.s)}mm"/>',
        f'<param name="mdWirePad" value="{_f(g.s)}mm"/>',
        f'<param name="mdWireVia" value="{_f(g.s)}mm"/>',
        f'<param name="mdPadPad" value="{_f(g.s)}mm"/>',
        f'<param name="mdPadVia" value="{_f(g.s)}mm"/>',
        f'<param name="mdViaVia" value="{_f(g.s)}mm"/>',
        f'<param name="msWidth" value="{_f(min(g.w, 0.127))}mm"/>',
        f'<param name="msDrill" value="{_f(min(p.via_drill, 0.2))}mm"/>',
        '<param name="rvViaOuter" value="0"/><param name="rvViaInner" value="0"/>',
        f'<param name="rlMinViaOuter" value="{_f((p.via_pad - p.via_drill) / 2)}mm"/>',
        f'<param name="rlMaxViaOuter" value="{_f((p.via_pad - p.via_drill) / 2)}mm"/>',
        f'<param name="rlMinViaInner" value="{_f((p.via_pad - p.via_drill) / 2)}mm"/>',
        f'<param name="rlMaxViaInner" value="{_f((p.via_pad - p.via_drill) / 2)}mm"/>',
        '</designrules>',
        '<autorouter/>',
        '<elements>',
    ]
    for pad in layout.pads:
        out.append(f'<element name={quoteattr(pad.name)} library="pegacoil" package="ANSCHLUSS" value=""'
                   f' x="{_f(c + pad.x)}" y="{_f(c + pad.y)}"/>')
    out += ['</elements>', '<signals>']
    for net, ph in enumerate(PHASES, start=1):
        out.append(f'<signal name="{ph}">')
        for pad in layout.pads:
            if pad.net == net:
                out.append(f'<contactref element={quoteattr(pad.name)} pad="1"/>')
        for t in layout.tracks:
            if t.net != net:
                continue
            layer = cl[t.layer]
            for pr in t.path:
                a, b = ends(pr)
                if pr[0] == 'L':
                    if math.dist(a, b) >= 1e-4:
                        out.append(wire(a, b, t.width, layer))
                elif abs(pr[3] - pr[2]) * pr[1] >= 1e-4:
                    r = pr[1]
                    for s0, s1 in _arc_pieces(r, pr[2], pr[3]):
                        pa = (r * math.cos(s0), r * math.sin(s0))
                        pb = (r * math.cos(s1), r * math.sin(s1))
                        out.append(wire(pa, pb, t.width, layer, math.degrees(s1 - s0)))
        for v in layout.vias:
            if v.net == net:
                out.append(f'<via x="{_f(c + v.x)}" y="{_f(c + v.y)}" extent="1-16" drill="{_f(p.via_drill)}"'
                           f' diameter="{_f(p.via_pad)}"/>')
        out.append('</signal>')
    out += ['</signals>', '</board>', '</drawing>', '</eagle>']
    return '\n'.join(out) + '\n'
