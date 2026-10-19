"""Ergebnis als Text (deutsch) – für das Fusion-Fenster und die Berichtsdatei."""

import math

from .design import ALPHA_CU, VIA_AMPS, _better, layer_thickness


def _n(x, d=2):
    return f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')


def summary(d, results=None, r_exact=None):
    g, p = d.geo, d.p
    ts = layer_thickness(d.layers, d.outer_oz, p.inner_oz)
    r_ph = r_exact if r_exact else d.r_phase
    r_ll = 2 * r_ph
    hot = 1 + ALPHA_CU * p.max_rise
    r_m = (g.r1 + g.r2) / 2
    pitch = 2 * math.pi * r_m / d.poles
    mag = min(0.85 * pitch, 0.9 * (g.r2 - g.r1))
    mot = (
        f'Motorleistung (mechanisch, dauerhaft): ca. {_n(d.p_mech, 1)} W'
        f' – {_n(d.torque * 1000, 1)} mNm bei {_n(d.rpm, 0)} U/min ({_n(p.voltage_v, 1)} V)'
    )
    if d.p_wanted <= 0:
        head = [mot, '  (automatisch: das Meiste, was diese Größe dauerhaft schafft)']
    elif d.p_wanted > d.p_top:
        head = [f'Gewünscht {_n(d.p_wanted, 1)} W – passt auf diese Größe nicht dauerhaft, gerechnet mit dem Möglichen:', mot]
    else:
        head = [mot]
    head.append(
        f'Elektrisch aufgenommen: {_n(d.p_in, 1)} W ({_n(d.current, 2)} A), davon Wärme im Kupfer {_n(d.p_cu, 1)} W'
    )
    L = head + [
        '',
        f'Platine: Ø {_n(p.outer_d, 1)} / Ø {_n(p.inner_d, 1)} mm, {d.layers} Lagen, {_n(p.board_t, 1)} mm',
        f'Kupfer: außen {_n(d.outer_oz, 1)} oz ({_n(ts[0] * 1000, 0)} µm)'
        + (f', innen {_n(p.inner_oz, 1)} oz ({_n(ts[1] * 1000, 1)} µm)' if d.layers > 2 else ''),
        f'Spulen: {d.coils} (3 Phasen × {d.coils // 3} in Reihe), Magnetpole: {d.poles}',
        f'Windungen: {d.turns} je Lage, {d.turns * d.layers} je Spule',
        f'Bahnbreite {_n(d.w, 3)} mm, Abstand {_n(d.s, 3)} mm',
        f'Spulenbereich: r = {_n(g.r1, 1)} … {_n(g.r2, 1)} mm',
        '',
        f'Widerstand je Phase: {_n(r_ph, 2)} Ω (20 °C), {_n(r_ph * hot, 2)} Ω warm (+{_n(p.max_rise, 0)} K)',
        f'Zwischen zwei Anschlüssen (Stern): {_n(r_ll, 2)} Ω',
        f'Dauerstrom: {_n(d.current, 2)} A, höchstens {_n(d.i_max, 2)} A'
        + (' – Treiber muss den Anlaufstrom darauf begrenzen' if d.limited else ''),
        f'Verlustleistung Kupfer: {_n(d.p_cu, 1)} W → Platine ca. +{_n(d.rise, 0)} K'
        f' (zulässig +{_n(p.max_rise, 0)} K, ruhende Luft)',
        '',
        f'Drehmomentkonstante (geschätzt, B = {_n(p.b_gap, 2)} T): {_n(d.kt * 1000, 2)} mNm/A',
        f'Dauer-Drehmoment: {_n(d.torque * 1000, 1)} mNm',
        f'Leerlaufdrehzahl bei {_n(p.voltage_v, 1)} V: ca. {_n(d.rpm0, 0)} U/min',
        '',
        f'Magnete: {d.poles} Stück, N/S abwechselnd, auf r ≈ {_n(r_m, 1)} mm',
        f'  z. B. Scheiben Ø {_n(math.floor(mag), 0)} mm (Polteilung {_n(pitch, 1)} mm), Luftspalt ≤ 1 mm',
        '  Rückschlussscheibe aus Stahl hinter den Magneten erhöht B deutlich.',
        '',
        'Anschlüsse: U1/U2, V1/V2, W1/W2 – Stern: U2+V2+W2 verbinden, Dreieck: U2–V1, V2–W1, W2–U1.',
    ]
    warn = []
    if d.outer_oz > 2 or (d.layers > 2 and p.inner_oz > 2):
        warn.append(
            f'Heavy Copper ({_n(d.outer_oz, 0)} oz außen'
            + (f', {_n(p.inner_oz, 0)} oz innen' if d.layers > 2 else '')
            + f'): Mindestbahn/-abstand {_n(d.s, 2)} mm angenommen, Platine {_n(p.board_t, 1)} mm – '
            'vor der Bestellung mit den Fertigerregeln (z. B. PCBWay) abgleichen. '
            'Wirbelstromverluste im dicken Kupfer sind nicht gerechnet.'
        )
    if d.rpm0 > p.max_rpm:
        warn.append(
            f'Achtung: Leerlauf {_n(d.rpm0, 0)} U/min – für diese Größe ist {_n(p.voltage_v, 0)} V zu viel, Spannung senken.'
        )
    if d.current > VIA_AMPS:
        warn.append(f'Achtung: {_n(d.current, 1)} A durch einzelne Durchkontaktierungen (≈ {_n(VIA_AMPS, 0)} A) – nur kurzzeitig.')
    if warn:
        L += [''] + warn
    if results:
        L += ['', 'Vergleich (jeweils beste Spulenzahl):', '  Lagen  außen  innen  Spulen  Wdg/Lage  Bahn mm   Ω Phase   mNm  W Welle']
        best = {}
        for r in results:
            k = (r.layers, r.outer_oz, r.p.inner_oz if r.layers > 2 else 0.0)
            if k not in best or _better(r, best[k]):
                best[k] = r
        for k in sorted(best):
            r = best[k]
            mark = ' ←' if r is d or (r.layers, r.outer_oz, r.coils, r.p.inner_oz) == (d.layers, d.outer_oz, d.coils, d.p.inner_oz) else ''
            inner = _n(r.p.inner_oz, 1) + ' oz' if r.layers > 2 else '    –'
            L.append(
                f'  {r.layers:5d}  {_n(r.outer_oz, 0):>2} oz  {inner:>6}  {r.coils:6d}  {r.turns:8d}  {_n(r.w, 3):>7}  {_n(r.r_phase, 2):>8}  {_n(r.torque * 1000, 1):>6}  {_n(r.p_mech, 1):>7}{mark}'
            )
    return '\n'.join(L)
