"""Ergebnis als Text (deutsch) – für das Fusion-Fenster und die Berichtsdatei."""

import math

from .design import ALPHA_CU, COOLING, HALBACH_SEGMENTS, MAGNETS, VIA_AMPS, _better, layer_thickness
from .rotor import IRON_T, stack


def _n(x, d=2):
    return f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')


def cooling_name(h):
    return next((k for k, v in COOLING.items() if abs(v - h) < 1e-6), 'eigene Kühlung')


def torque_text(t):
    """Drehmoment lesbar: unter 1 Nm in mNm, sonst in Nm."""
    return f'{_n(t * 1000, 1)} mNm' if t < 1 else f'{_n(t, 2)} Nm'


def summary(d, results=None, r_exact=None):
    g, p = d.geo, d.p
    ts = layer_thickness(d.layers, d.outer_oz, p.inner_oz)
    r_ph = r_exact if r_exact else d.r_phase
    r_ll = 2 * r_ph
    hot = 1 + ALPHA_CU * p.max_rise
    r_m = (g.r1 + g.r2) / 2
    pitch = 2 * math.pi * r_m / d.poles
    mot = (
        f'Motorleistung (mechanisch, dauerhaft): ca. {_n(d.p_mech, 1)} W'
        f' – {torque_text(d.torque)} bei {_n(d.rpm, 0)} U/min ({_n(p.voltage_v, 1)} V)'
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
    phase = p.boards == 3
    if p.b_gap > 0:
        field = f'Flussdichte vorgegeben: {_n(p.b_gap, 2)} T (Mittel)'
    else:
        kind = (f'Halbach, {HALBACH_SEGMENTS // 2} Segmente je Pol' if p.rotor == 'halbach'
                else f'auf Stahlrückschluss, Polbedeckung {_n(p.pole_arc * 100, 0)} %')
        field = (f'Magnete {p.magnet} ({_n(MAGNETS.get(p.magnet, 1.3), 2)} T), {_n(p.magnet_h, 1)} mm dick, beidseitig {kind};'
                 f' Spalt Magnet–Magnet {_n(p.board_t + 2 * p.clearance, 1)} mm → B ≈ {_n(d.b1, 2)} T Spitze,'
                 f' {_n(d.b, 2)} T Mittel')
    st = stack(d)
    if p.rotor == 'halbach':
        mags = (f'{len(st.discs)} Rotorscheiben, {st.magnet_count} Halbach-Segmente ({HALBACH_SEGMENTS // 2} je Pol,'
                f' innere Scheiben zwei Lagen Rücken an Rücken)')
    else:
        mags = (f'{len(st.discs)} Rotorscheiben, {st.magnet_count} Magnete N/S abwechselnd'
                f' (außen auf {_n(IRON_T, 0)} mm Stahl, innen durchgehend)')
    mags += f'; Stapelhöhe {_n(st.height, 1)} mm, Welle Ø {_n(st.shaft_d, 0)} mm'
    if phase:
        build = [
            f'Aufbau: 3 gleiche Platinen, je Phase eine (gestapelt, jede in eigenem Luftspalt) – 3 Stück bestellen',
            f'  Platine 2 um {_n(240 / d.coils, 2)}°, Platine 3 um {_n(480 / d.coils, 2)}° gegen Platine 1 verdreht'
            ' einbauen (120° elektrisch)',
            f'Spulen: {d.coils} je Platine, alle in Reihe, benachbarte gegensinnig (eine Spule je Pol)',
        ]
        conn = 'Anschlüsse je Platine P1/P2: Platine 1 = U, 2 = V, 3 = W – Stern: alle P2 verbinden.'
    else:
        build = [f'Spulen: {d.coils} (3 Phasen × {d.coils // 3} in Reihe), Magnetpole: {d.poles}']
        conn = 'Anschlüsse: U1/U2, V1/V2, W1/W2 – Stern: U2+V2+W2 verbinden, Dreieck: U2–V1, V2–W1, W2–U1.'
    L = head + [
        '',
        f'Platine: Ø {_n(p.outer_d, 1)} / Ø {_n(p.inner_d, 1)} mm, {d.layers} Lagen, {_n(p.board_t, 1)} mm',
        f'Kupfer: außen {_n(d.outer_oz, 1)} oz ({_n(ts[0] * 1000, 0)} µm)'
        + (f', innen {_n(p.inner_oz, 1)} oz ({_n(ts[1] * 1000, 1)} µm)' if d.layers > 2 else ''),
        *build,
        f'Lagen geschaltet: {g.par} Paar(e) parallel' + (f' × {g.ns} Gruppen in Reihe' if g.ns > 1 else '')
        + (' (alle Lagen in Reihe)' if g.par == 1 and g.ns > 1 else ''),
        f'Windungen: {d.turns} je Lage, {d.turns * 2 * g.ns} je Spule wirksam',
        f'Bahnbreite {_n(d.w, 3)} mm, Abstand {_n(d.s, 3)} mm',
        f'Spulenbereich: r = {_n(g.r1, 1)} … {_n(g.r2, 1)} mm',
        '',
        f'Widerstand je Phase: {_n(r_ph, 2)} Ω (20 °C), {_n(r_ph * hot, 2)} Ω warm (+{_n(p.max_rise, 0)} K)',
        f'Zwischen zwei Anschlüssen (Stern): {_n(r_ll, 2)} Ω',
        f'Dauerstrom: {_n(d.current, 2)} A, höchstens {_n(d.i_max, 2)} A'
        + (' – Treiber muss den Anlaufstrom darauf begrenzen' if d.limited else ''),
        f'Verlustleistung Kupfer: {_n(d.p_cu, 1)} W → Platinen ca. +{_n(d.rise, 0)} K'
        f' (zulässig +{_n(p.max_rise, 0)} K, {cooling_name(p.h_air)}, {_n(p.h_air, 0)} W/m²K)',
        '',
        f'Drehmomentkonstante: {_n(d.kt * 1000, 2)} mNm/A',
        f'Dauer-Drehmoment: {torque_text(d.torque)}',
        f'Leerlaufdrehzahl bei {_n(p.voltage_v, 1)} V: ca. {_n(d.rpm0, 0)} U/min',
        '',
        field,
        f'{mags}, auf r = {_n(g.r1, 1)} … {_n(g.r2, 1)} mm (Polteilung {_n(pitch, 1)} mm in der Mitte)',
        '',
        conn,
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
        L += ['', 'Vergleich (jeweils beste Spulenzahl):', '  Lagen  außen  innen  Spulen  Wdg/Lage  Bahn mm   Ω Phase      Nm  W Welle']
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
                f'  {r.layers:5d}  {_n(r.outer_oz, 0):>2} oz  {inner:>6}  {r.coils:6d}  {r.turns:8d}  {_n(r.w, 3):>7}  {_n(r.r_phase, 2):>8}  {_n(r.torque, 3):>7}  {_n(r.p_mech, 1):>7}{mark}'
            )
    return '\n'.join(L)
