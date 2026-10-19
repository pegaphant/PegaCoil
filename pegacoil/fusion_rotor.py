"""Zeichnet Rotor und Stapel in Fusion: je Rotorscheibe eine Komponente (Träger, Magnete als einzelne Körper,
ggf. Stahlrückschluss), je Platine ein Stator-Platzhalter (mit Anschlussbohrungen, um den Einbauwinkel verdreht)
und die Welle. Grundlage ist die Bauteilliste aus rotor.stack()."""

import math

import adsk.core
import adsk.fusion

from .rotor import stack

CM = 0.1  # Fusion rechnet intern in cm

COLORS = {  # Darstellung (falls in der Bibliothek vorhanden)
    'up': 'Paint - Enamel Glossy (Red)',  # ↑ axial bzw. N oben
    'down': 'Paint - Enamel Glossy (Blue)',  # ↓ axial bzw. S oben
    'side': 'Paint - Enamel Glossy (Yellow)',  # tangential (Halbach)
    'carrier': 'Aluminum - Satin',
    'iron': 'Steel - Satin',
    'stator': 'Paint - Enamel Glossy (Green)',
}


def _p(x, y):
    return adsk.core.Point3D.create(x * CM, y * CM, 0)


def _appearance(design, key):
    name = COLORS[key]
    try:
        a = design.appearances.itemByName(name)
        if a:
            return a
        lib = adsk.core.Application.get().materialLibraries.itemByName('Fusion Appearance Library')
        src = lib.appearances.itemByName(name) if lib else None
        return design.appearances.addByCopy(src, name) if src else None
    except Exception:
        return None


def _paint(body, appearance):
    if appearance:
        try:
            body.appearance = appearance
        except Exception:
            pass


def _plane(comp, z):
    if abs(z) < 1e-9:
        return comp.xYConstructionPlane
    pin = comp.constructionPlanes.createInput()
    pin.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(z * CM))
    plane = comp.constructionPlanes.add(pin)
    plane.isLightBulbOn = False
    return plane


def _extrude(comp, profiles, height, op=adsk.fusion.FeatureOperations.NewBodyFeatureOperation):
    ext = comp.features.extrudeFeatures.createInput(profiles, op)
    ext.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height * CM))
    return comp.features.extrudeFeatures.add(ext)


def _annulus(comp, z0, z1, r_out, r_in, name, holes=()):
    sk = comp.sketches.add(_plane(comp, z0))
    sk.name = name
    c = sk.sketchCurves.sketchCircles
    c.addByCenterRadius(_p(0, 0), r_out * CM)
    if r_in > 0:
        c.addByCenterRadius(_p(0, 0), r_in * CM)
    for x, y, r in holes:
        c.addByCenterRadius(_p(x, y), r * CM)
    prof = max(sk.profiles, key=lambda pr: pr.profileLoops.count)
    body = _extrude(comp, prof, z1 - z0).bodies.item(0)
    body.name = name
    return body


def _magnet_layer(comp, mags, r_in, r_out):
    """Alle Magnete einer Lage (gleiches z) als Kreisringsegmente – ein Extrude, ein Körper je Segment."""
    z0, z1 = mags[0].z0, mags[0].z1
    sk = comp.sketches.add(_plane(comp, z0))
    sk.name = f'Magnete z {z0:.1f}'
    sk.isComputeDeferred = True
    arcs, lines = sk.sketchCurves.sketchArcs, sk.sketchCurves.sketchLines
    for m in mags:
        a0, a1 = math.radians(m.a0), math.radians(m.a1)
        pi0, po0 = _p(r_in * math.cos(a0), r_in * math.sin(a0)), _p(r_out * math.cos(a0), r_out * math.sin(a0))
        pi1, po1 = _p(r_in * math.cos(a1), r_in * math.sin(a1)), _p(r_out * math.cos(a1), r_out * math.sin(a1))
        outer = arcs.addByCenterStartSweep(_p(0, 0), po0, a1 - a0)
        inner = arcs.addByCenterStartSweep(_p(0, 0), pi0, a1 - a0)
        lines.addByTwoPoints(inner.startSketchPoint, outer.startSketchPoint)
        lines.addByTwoPoints(inner.endSketchPoint, outer.endSketchPoint)
    sk.isComputeDeferred = False
    profs = adsk.core.ObjectCollection.create()
    for pr in sk.profiles:
        profs.add(pr)
    bodies = list(_extrude(comp, profs, z1 - z0).bodies)
    # Namen nach Winkel des Schwerpunkts zuordnen (Reihenfolge der Körper ist nicht festgelegt)
    for b in bodies:
        bb = b.boundingBox
        cx, cy = (bb.minPoint.x + bb.maxPoint.x) / 2, (bb.minPoint.y + bb.maxPoint.y) / 2
        ang = math.degrees(math.atan2(cy, cx)) % 360
        m = min(mags, key=lambda m: abs(((m.a0 + m.a1) / 2 - ang + 180) % 360 - 180))
        b.name = f'Magnet {(m.a0 + m.a1) / 2:.0f}° {m.label}'
    return bodies


def draw(design, d):
    """Neue Komponente „PegaCoil Motor“ mit Rotorscheiben, Statoren und Welle. Gibt die Komponente zurück."""
    st = stack(d)
    g, p = d.geo, d.p
    root = design.rootComponent
    motor = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
    motor.name = f'PegaCoil Motor Ø{p.outer_d:g} {d.poles}P {"3 Platinen" if p.boards == 3 else "1 Platine"}'
    look = {k: _appearance(design, k) for k in COLORS}
    r_in, r_out = st.r_mag
    for disc in st.discs:
        comp = motor.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        comp.name = disc.name
        cz0, cz1 = disc.z0, disc.z1
        if disc.iron:  # Träger nur neben den Magneten, Stahl darunter bzw. darüber
            cz0, cz1 = (disc.iron[1], disc.z1) if disc.iron[0] <= disc.z0 + 1e-9 else (disc.z0, disc.iron[0])
            _paint(_annulus(comp, disc.iron[0], disc.iron[1], disc.r_out, disc.r_in, 'Rückschluss (Stahl)'), look['iron'])
        carrier = _annulus(comp, cz0, cz1, disc.r_out, disc.r_in, 'Träger (unmagnetisch)')
        _paint(carrier, look['carrier'])
        layers = {}
        for m in disc.magnets:
            layers.setdefault((round(m.z0, 4), round(m.z1, 4)), []).append(m)
        tools = adsk.core.ObjectCollection.create()
        for mags in layers.values():
            for b in _magnet_layer(comp, mags, r_in, r_out):
                key = 'up' if ('↑' in b.name or 'N oben' in b.name) else 'down' if ('↓' in b.name or 'S oben' in b.name) else 'side'
                _paint(b, look[key])
                tools.add(b)
        if tools.count:  # Taschen in den Träger
            ci = comp.features.combineFeatures.createInput(carrier, tools)
            ci.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
            ci.isKeepToolBodies = True
            comp.features.combineFeatures.add(ci)
    # Statoren: Platzhalter-Scheiben mit den Anschlussbohrungen P1/P2 bzw. U1…W2, um den Einbauwinkel verdreht
    pad_holes = []
    if p.boards == 3:
        for c in (0, 1):
            x, y = g.pt(g.r_pad, g.dl_pad)
            t = 2 * g.phi * c
            pad_holes.append((x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t), p.pad_drill / 2))
    for s in st.stators:
        m = adsk.core.Matrix3D.create()
        m.setToRotation(math.radians(s.angle), adsk.core.Vector3D.create(0, 0, 1), adsk.core.Point3D.create(0, 0, 0))
        comp = motor.occurrences.addNewComponent(m).component
        comp.name = f'{s.name} – {s.angle:.2f}°'
        _paint(_annulus(comp, s.z0, s.z1, s.r_out, s.r_in, 'Platine', pad_holes), look['stator'])
    # Welle
    comp = motor.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
    comp.name = f'Welle Ø{st.shaft_d:g}'
    _annulus(comp, -10, st.height + 10, st.shaft_d / 2, 0, 'Welle')
    return motor
