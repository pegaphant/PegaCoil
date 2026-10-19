"""Zeichnet eine Auslegung in Fusion: Leiterplatte als Körper, je Lage eine Skizze (Bahnmitten)."""

import math

import adsk.core
import adsk.fusion

from .kicad import layer_names
from .layout import ends

CM = 0.1  # Fusion rechnet intern in cm


def _p3(pt, z=0.0):
    return adsk.core.Point3D.create(pt[0] * CM, pt[1] * CM, z)


def draw(design, layout, one_coil=False, body=True):
    d = layout.design
    g, p = d.geo, d.p
    root = design.rootComponent
    try:
        comp = root.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
        comp.name = f'PegaCoil Ø{p.outer_d:g}-Ø{p.inner_d:g} {d.coils}S{d.poles}P {g.n}L'
    except RuntimeError:
        comp = root  # „Part Design“-Dokument: nur eine Komponente erlaubt → direkt in die Hauptkomponente
    t = p.board_t * CM

    if body:
        sk = comp.sketches.add(comp.xYConstructionPlane)
        sk.name = 'Leiterplatte'
        circles = sk.sketchCurves.sketchCircles
        circles.addByCenterRadius(_p3((0, 0)), p.outer_d / 2 * CM)
        circles.addByCenterRadius(_p3((0, 0)), p.inner_d / 2 * CM)
        prof = next((pr for pr in sk.profiles if pr.profileLoops.count == 2), None)
        if prof:
            ext = comp.features.extrudeFeatures.addSimple(
                prof, adsk.core.ValueInput.createByReal(t), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ext.bodies.item(0).name = 'Leiterplatte'

    names = layer_names(g.n)
    planes = comp.constructionPlanes
    for li in range(g.n):
        z = t * (1 - li / (g.n - 1))
        pin = planes.createInput()
        pin.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(z))
        plane = planes.add(pin)
        plane.name = f'Lage {li + 1}'
        plane.isLightBulbOn = False
        sk = comp.sketches.add(plane)
        sk.name = f'Lage {li + 1} ({names[li]})'
        sk.isComputeDeferred = True
        lines = sk.sketchCurves.sketchLines
        arcs = sk.sketchCurves.sketchArcs
        center = _p3((0, 0))
        for tr in layout.tracks:
            if tr.layer != li or (one_coil and tr.coil not in (0, -1)):
                continue
            for pr in tr.path:
                a, b = ends(pr)
                if pr[0] == 'L':
                    if math.dist(a, b) > 1e-4:
                        lines.addByTwoPoints(_p3(a), _p3(b))
                elif abs(pr[3] - pr[2]) * pr[1] > 1e-4:
                    arcs.addByCenterStartSweep(center, _p3(a), pr[3] - pr[2])
        circles = sk.sketchCurves.sketchCircles
        for v in layout.vias:
            if not one_coil or v.coil == 0:
                circles.addByCenterRadius(_p3((v.x, v.y)), g.vr * CM)
        for pad in layout.pads:
            circles.addByCenterRadius(_p3((pad.x, pad.y)), g.pad_r * CM)
        sk.isComputeDeferred = False
        sk.arePointsShown = False  # sonst je Bahnende ein weißer Punkt
    return comp
