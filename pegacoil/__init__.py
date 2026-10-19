"""PegaCoil – Stator-Leiterplatten für PCB-Motoren auslegen (ohne Fusion-Abhängigkeit)."""

from . import design, layout, drc, kicad, eagle, report  # noqa: F401
from .design import RHO_CU, Params, layer_thickness, optimize


def run(params):
    """Auslegen, Bahnen erzeugen, prüfen. Ergebnis: (design, layout, Bericht, Fehlerliste)."""
    best, results = optimize(params)
    lay = layout.build(best)
    ts = layer_thickness(best.layers, best.outer_oz, best.p.inner_oz)
    r_ph = max(layout.phase_resistance(lay, RHO_CU, ts))
    nc = best.coils
    errors = drc.check(lay, coils={0, 1, 2, 3, 4 % nc, nc - 1})
    text = report.summary(best, results, r_ph)
    if errors:
        text += '\n\nAbstandsprüfung: ' + str(len(errors)) + ' Fehler\n  ' + '\n  '.join(errors[:8])
    else:
        text += '\n\nAbstandsprüfung: in Ordnung'
    return best, lay, text, errors
