"""PegaCoil – Fusion-Add-in: Stator-Leiterplatte für einen PCB-Motor auslegen und zeichnen."""

import dataclasses
import importlib
import math
import os
import tempfile
import threading
import time
import traceback

import adsk.core
import adsk.fusion

from . import pegacoil
from .pegacoil import design as _design, drc as _drc, eagle as _eagle, kicad as _kicad, layout as _layout, report as _report

from .pegacoil import fusion_draw, fusion_rotor, rotor as _rotor, update as _update  # noqa: E402


def _reload_modules():
    """Rechenmodule neu einlesen (nach einem Update bzw. weil Fusion Untermodule beim Neustart des Add-ins im
    Speicher behält). Neuladen darf den Start nie verhindern (wie PegaCAM)."""
    for m in (_design, _layout, _drc, _kicad, _eagle, _rotor, _report, _update, pegacoil, fusion_draw, fusion_rotor):
        try:
            importlib.reload(m)
        except Exception:
            pass


_reload_modules()

CMD_ID = 'PegaCoil_Stator'
PANEL_ID = 'SolidScriptsAddinsPanel'
HERE = os.path.dirname(os.path.abspath(__file__))

_app = None
_ui = None
_handlers = []
_last = {'key': None, 'result': None}

LAYERS = [('Automatisch', 0)] + [(str(n), n) for n in _design.LAYER_CHOICES]
COILS = [('Automatisch', 0)] + [(str(c), c) for c in sorted(set(_design.COIL_CHOICES) | set(_design.PHASE_COIL_CHOICES))]
BOARDS = [('3 Platinen (je Phase eine)', 3), ('1 Platine (alle 3 Phasen)', 1)]
ROTORS = [('Halbach (beidseitig)', 'halbach'), ('Magnete auf Stahlrückschluss (beidseitig)', 'iron')]
GRADES = [(g, g) for g in reversed(list(_design.MAGNETS))]  # N52 zuerst
COOLINGS = [(f'{k} ({v:g} W/m²K)', v) for k, v in _design.COOLING.items()]
OUTER = [('Automatisch (bis 13 oz)', 0.0)] + [(f'{o:g} oz ({o * 35:g} µm)', o) for o in _design.OZ_CHOICES]
INNER = [('Automatisch (wie außen, bis 6 oz)', 0.0)] + [(f'{o:g} oz ({o * 35:g} µm)'.replace('.', ','), o) for o in _design.INNER_OZ_CHOICES]


def _dropdown(inputs, cid, name, items, selected=0):
    dd = inputs.addDropDownCommandInput(cid, name, adsk.core.DropDownStyles.TextListDropDownStyle)
    for i, (label, _) in enumerate(items):
        dd.listItems.add(label, i == selected, '')
    return dd


def _choice(inputs, cid, items):
    sel = inputs.itemById(cid).selectedItem
    return dict(items)[sel.name] if sel else items[0][1]


def _params(inputs):
    def val(cid):
        return inputs.itemById(cid).value

    return _design.Params(
        outer_d=val('od') * 10,
        inner_d=val('id') * 10,
        power_w=val('power'),
        voltage_v=val('volt'),
        layers=_choice(inputs, 'layers', LAYERS),
        coils=_choice(inputs, 'coils', COILS),
        outer_oz=_choice(inputs, 'outer_oz', OUTER),
        inner_oz=_choice(inputs, 'inner_oz', INNER),
        b_gap=val('b_gap'),
        boards=_choice(inputs, 'boards', BOARDS),
        rotor=_choice(inputs, 'rotor', ROTORS),
        magnet=_choice(inputs, 'magnet', GRADES),
        magnet_h=val('magnet_h') * 10,
        clearance=val('clearance'),
        h_air=_choice(inputs, 'cooling', COOLINGS),
        max_rise=val('rise'),
        speed=val('speed'),
        min_eff=val('min_eff') / 100,
        max_rpm=val('max_rpm'),
        min_trace=val('min_trace'),
        min_space=val('min_space'),
        via_drill=val('via_drill'),
        via_pad=val('via_pad'),
        pad_drill=val('pad_drill'),
        pad_d=val('pad_d'),
    )


def _compute(inputs):
    p = _params(inputs)
    key = repr(p)
    if _last['key'] != key:
        _last['result'] = pegacoil.run(p)
        _last['key'] = key
    return _last['result']


SIZE_IDS = ('od', 'id', 'volt', 'speed', 'cooling', 'boards', 'rotor', 'magnet', 'magnet_h', 'clearance', 'layers', 'coils', 'outer_oz',
            'inner_oz', 'b_gap', 'rise', 'min_eff', 'max_rpm',
            'min_trace', 'min_space', 'via_drill', 'via_pad', 'pad_drill', 'pad_d')
_sync = {}  # Werte, die PegaCoil selbst gesetzt hat (deren Änderungsereignis wird übergangen)


def _set(inputs, cid, value, expression=None):
    inp = inputs.itemById(cid)
    _sync[cid] = value
    if expression:
        inp.expression = expression
    else:
        inp.value = value


def _ours(inp):
    v = _sync.pop(inp.id, None)
    return v is not None and abs(inp.value - v) < 1e-6


def _motor_line(d):
    n = _report._n
    return (
        f'<b>{n(d.p_mech, 1)} W</b> an der Welle · Aufnahme <b>{n(d.p_in, 1)} W</b> ({n(d.current, 2)} A)<br>'
        f'Drehmoment <b>{_report.torque_text(d.torque)}</b> dauerhaft bei {n(d.rpm, 0)} U/min,'
        f' Spitze <b>{_report.torque_text(d.torque_peak)}</b> · Leerlauf {n(d.rpm0, 0)} U/min<br>'
        f'{"3 Platinen" if d.p.boards == 3 else "1 Platine"}, {d.layers} Lagen, {n(d.outer_oz, 0)} oz, {d.coils} Spulen,'
        f' {d.poles} Pole, B {n(d.b1, 2)} T, Erwärmung +{n(d.rise, 0)} K'
    )


LIVE_EVENT = 'PegaCoil_Live'
_live_state = {'gen': 0, 'inputs': None, 'result': None}
_live_lock = threading.Lock()


def _live(inputs, changed):
    """Größe/Lagen/Spannung geändert → Leistung eintragen; Leistung geändert → Größe einstellen.
    Gerechnet wird im Hintergrund (das Fenster friert nicht ein); nur die letzte Eingabe zählt."""
    _live_state['gen'] += 1
    _live_state['inputs'] = inputs
    gen = _live_state['gen']
    p = _params(inputs)
    inputs.itemById('motor').formattedText = '<i>rechne …</i>'
    threading.Thread(target=_live_worker, args=(gen, p, changed), daemon=True).start()


def _live_worker(gen, p, changed):
    """Läuft im Hintergrund-Thread: nur reine Rechnung, keine Fusion-API."""
    with _live_lock:  # eine Rechnung nach der anderen; veraltete gar nicht erst anfangen
        if gen != _live_state['gen']:
            return
        res = {'gen': gen}
        try:
            if changed == 'power':
                if p.power_w > 0:
                    od, _ = _design.size_for_power(p, p.power_w)
                    if abs(od - p.outer_d) > 1e-6:
                        res['od'] = od
                        p = dataclasses.replace(p, outer_d=od)
            else:
                top = math.floor(_design.top_power(p) * 10) / 10
                if abs(top - p.power_w) > 1e-6:
                    res['power'] = top
                p = dataclasses.replace(p, power_w=top)
            d, results = _design.optimize(p)
            res['motor'] = _motor_line(d)
            res['text'] = _report.summary(d, results)
        except ValueError as e:
            res['motor'] = res['text'] = str(e)
        except Exception:
            res['motor'] = 'Fehler bei der Rechnung'
            res['text'] = traceback.format_exc()
    if gen == _live_state['gen']:
        _live_state['result'] = res
        _app.fireCustomEvent(LIVE_EVENT, str(gen))


class LiveResultHandler(adsk.core.CustomEventHandler):
    """Ergebnis der Hintergrund-Rechnung im Hauptthread ins Fenster schreiben."""

    def notify(self, args):
        try:
            res, inputs = _live_state['result'], _live_state['inputs']
            if not res or not inputs or res['gen'] != _live_state['gen']:
                return
            if 'od' in res:
                _set(inputs, 'od', res['od'] / 10, f"{res['od']:g} mm")
            if 'power' in res:
                _set(inputs, 'power', res['power'])
            inputs.itemById('motor').formattedText = res['motor']
            _show(inputs, res['text'])
        except Exception:
            pass  # Fenster inzwischen geschlossen


def _show(inputs, text):
    box = inputs.itemById('result')
    box.formattedText = '<pre>' + text.replace('&', '&amp;').replace('<', '&lt;') + '</pre>'


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.setDialogInitialSize(560, 760)
            inputs = cmd.commandInputs
            changed = _update.take_pulled()  # beim Start im Hintergrund aktualisiert → neuen Stand laden
            if changed:
                _reload_modules()
            info = _update.status_text()
            if changed:
                info += ' – <b>eben aktualisiert</b>'
                if 'PegaCoil.py' in changed or 'PegaCoil.manifest' in changed:
                    info += ' (Fenster/Knopf erst nach Fusion-Neustart)'
            inputs.addTextBoxCommandInput('version', '', info, 1, True)
            inputs.addValueInput('od', 'Außendurchmesser', 'mm', adsk.core.ValueInput.createByString('60 mm'))
            inputs.addValueInput('id', 'Innendurchmesser', 'mm', adsk.core.ValueInput.createByString('10 mm'))
            inputs.addFloatSpinnerCommandInput('volt', 'Spannung (V)', '', 1, 400, 1, 24)
            inputs.addFloatSpinnerCommandInput('speed', 'Nenndrehzahl U/min (0 = höchste Leistung)', '', 0, 30000, 100, 1500)
            inputs.addFloatSpinnerCommandInput('power', 'Motorleistung W (Welle, bei Nenndrehzahl)', '', 0, 5000, 1, 0)
            _dropdown(inputs, 'cooling', 'Kühlung', COOLINGS)
            _dropdown(inputs, 'boards', 'Aufbau', BOARDS)
            _dropdown(inputs, 'rotor', 'Magnete', ROTORS)
            _dropdown(inputs, 'magnet', 'Magnetsorte', GRADES)
            inputs.addValueInput('magnet_h', 'Magnetdicke je Seite', 'mm', adsk.core.ValueInput.createByString('5 mm'))
            _dropdown(inputs, 'layers', 'Lagen', LAYERS)
            _dropdown(inputs, 'coils', 'Spulen', COILS)
            _dropdown(inputs, 'outer_oz', 'Kupfer außen', OUTER)
            _dropdown(inputs, 'inner_oz', 'Kupfer innen', INNER)

            grp = inputs.addGroupCommandInput('adv', 'Erweitert')
            grp.isExpanded = False
            gi = grp.children
            gi.addFloatSpinnerCommandInput('clearance', 'Luft Platine–Magnet je Seite (mm)', '', 0.1, 5, 0.1, 0.5)
            gi.addFloatSpinnerCommandInput('b_gap', 'Flussdichte vorgeben T (0 = aus Magneten)', '', 0, 1.5, 0.05, 0)
            gi.addFloatSpinnerCommandInput('rise', 'Max. Erwärmung (K)', '', 5, 120, 5, 40)
            gi.addFloatSpinnerCommandInput('min_eff', 'Mindestwirkungsgrad % (nur ohne Nenndrehzahl)', '', 50, 99, 1, 80)
            gi.addFloatSpinnerCommandInput('max_rpm', 'Max. Leerlaufdrehzahl (U/min)', '', 1000, 200000, 1000, 10000)
            gi.addFloatSpinnerCommandInput('min_trace', 'Min. Bahnbreite mm (0 = auto)', '', 0, 2, 0.01, 0)
            gi.addFloatSpinnerCommandInput('min_space', 'Min. Abstand mm (0 = auto)', '', 0, 2, 0.01, 0)
            gi.addFloatSpinnerCommandInput('via_drill', 'Via-Bohrung (mm)', '', 0.15, 1, 0.05, 0.3)
            gi.addFloatSpinnerCommandInput('via_pad', 'Via-Pad (mm)', '', 0.3, 2, 0.05, 0.6)
            gi.addFloatSpinnerCommandInput('pad_drill', 'Anschluss-Bohrung (mm)', '', 0.5, 3, 0.1, 1.0)
            gi.addFloatSpinnerCommandInput('pad_d', 'Anschluss-Pad (mm)', '', 1, 5, 0.1, 2.0)

            inputs.addTextBoxCommandInput('motor', 'Motor', '', 3, True)
            inputs.addTextBoxCommandInput('result', 'Ergebnis', '', 18, True)
            _live(inputs, 'od')
            inputs.addBoolValueInput('pcb', 'Als PCB in Fusion Electronics öffnen', True, '', True)
            inputs.addBoolValueInput('rotor', 'Rotor & Stapel als 3D-Baugruppe (neues Design)', True, '', True)
            inputs.addBoolValueInput('draw', '3D-Skizzen in dieses Design zeichnen', True, '', False)
            inputs.addBoolValueInput('one_coil', '  nur eine Spule (schneller)', True, '', False)
            inputs.addBoolValueInput('body', '  Leiterplatte als Körper', True, '', True)
            inputs.addBoolValueInput('kicad', 'KiCad-Datei zusätzlich speichern', True, '', False)

            for h, ev in ((InputChangedHandler(), cmd.inputChanged), (ExecuteHandler(), cmd.execute)):
                ev.add(h)
                _handlers.append(h)
        except Exception:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        inp = args.input
        inputs = inp.parentCommand.commandInputs  # args.inputs ist in einer Gruppe nur die Gruppe
        if inp.id not in SIZE_IDS and inp.id != 'power':
            return
        if inp.id in ('od', 'power') and _ours(inp):
            return
        try:
            _live(inputs, inp.id)
        except Exception:
            _show(inputs, traceback.format_exc())


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        inputs = args.command.commandInputs
        try:
            d, lay, text, errors = _compute(inputs)
        except ValueError as e:
            _ui.messageBox(str(e), 'PegaCoil')
            return
        except Exception:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())
            return
        try:
            if errors and _ui.messageBox(
                f'Die Abstandsprüfung meldet {len(errors)} Fehler.\nTrotzdem fortfahren?',
                'PegaCoil',
                adsk.core.MessageBoxButtonTypes.YesNoButtonType,
            ) != adsk.core.DialogResults.DialogYes:
                return
            if inputs.itemById('pcb').value:
                _open_pcb(d, lay, text)
            if inputs.itemById('rotor').value:
                _new_rotor(d)
            if inputs.itemById('kicad').value:
                dlg = _ui.createFileDialog()
                dlg.title = 'KiCad-Platine speichern'
                dlg.filter = 'KiCad-Platine (*.kicad_pcb)'
                dlg.initialFilename = f'PegaCoil_{d.p.outer_d:g}x{d.p.inner_d:g}_{d.coils}S_{d.layers}L.kicad_pcb'
                if dlg.showSave() == adsk.core.DialogResults.DialogOK:
                    path = dlg.filename
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(_kicad.to_kicad(lay))
                    with open(os.path.splitext(path)[0] + '_Auslegung.txt', 'w', encoding='utf-8') as f:
                        f.write(text + '\n')
            if inputs.itemById('draw').value:
                des = adsk.fusion.Design.cast(_app.activeProduct)
                if not des:
                    _ui.messageBox('Bitte zuerst ein Konstruktions-Dokument öffnen.', 'PegaCoil')
                    return
                comp = fusion_draw.draw(des, lay, inputs.itemById('one_coil').value, inputs.itemById('body').value)
                _app.activeViewport.fit()
                _ui.messageBox(
                    f'Platine gezeichnet: Komponente „{comp.name}“ (Browser links).\n'
                    f'Je Lage eine Skizze „Lage 1 …“ mit den Leiterbahnen.',
                    'PegaCoil',
                )
        except Exception:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())


def _new_rotor(d):
    """Neues Design (Baugruppe) mit Rotorscheiben, Magneten, Statoren und Welle."""
    _app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    des = adsk.fusion.Design.cast(_app.activeProduct)
    for intent in (adsk.fusion.DesignIntentTypes.AssemblyDesignIntentType,
                   adsk.fusion.DesignIntentTypes.HybridDesignIntentType):
        try:
            des.designIntent = intent
            break
        except Exception:
            pass
    motor = fusion_rotor.draw(des, d)
    _app.activeViewport.fit()
    return motor


def _open_pcb(d, lay, text):
    """EAGLE-Platine schreiben, ins aktive Projekt (Ordner „PegaCoil“) hochladen und als PCB öffnen."""
    p = d.p
    name = f'PegaCoil_{p.outer_d:g}x{p.inner_d:g}_{d.coils}S_{d.layers}L_{d.p_mech:.0f}W' + ('_3Stk' if p.boards == 3 else '')
    out_dir = os.path.join(tempfile.gettempdir(), 'PegaCoil')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + '.brd')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(_eagle.to_eagle(lay, name))
    with open(os.path.join(out_dir, name + '_Auslegung.txt'), 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    proj = _app.data.activeProject
    root = proj.rootFolder
    folder = root.dataFolders.itemByName('PegaCoil') or root.dataFolders.add('PegaCoil')
    fut = folder.uploadFile(path)
    t_end = time.time() + 180
    while fut.uploadState == adsk.core.UploadStates.UploadProcessing and time.time() < t_end:
        adsk.doEvents()
        time.sleep(0.2)
    if fut.uploadState != adsk.core.UploadStates.UploadFinished or not fut.dataFile:
        _ui.messageBox(
            f'Hochladen nach Fusion hat nicht geklappt.\nDie Platine liegt hier und lässt sich über '
            f'Datei → Öffnen → „Von meinem Computer öffnen“ laden:\n{path}',
            'PegaCoil',
        )
        return
    _app.documents.open(fut.dataFile)


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _update.start()  # neue Version auf GitHub? Im Hintergrund prüfen und holen
        try:
            _app.unregisterCustomEvent(LIVE_EVENT)
        except Exception:
            pass
        ev = _app.registerCustomEvent(LIVE_EVENT)
        lh = LiveResultHandler()
        ev.add(lh)
        _handlers.append(lh)
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            try:
                cmd_def.deleteMe()
                cmd_def = None
            except Exception:
                pass  # läuft gerade (Fenster offen) → vorhandenen Befehl weiterverwenden
        if not cmd_def:
            cmd_def = _ui.commandDefinitions.addButtonDefinition(
                CMD_ID, 'PegaCoil', 'Stator-Leiterplatte für einen PCB-Motor auslegen', os.path.join(HERE, 'resources')
            )
        h = CreatedHandler()
        cmd_def.commandCreated.add(h)
        _handlers.append(h)
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel and not panel.controls.itemById(CMD_ID):
            ctrl = panel.controls.addCommand(cmd_def)
            ctrl.isPromoted = True  # Knopf direkt in der Leiste, nicht nur im Ausklappmenü
    except Exception:
        if _ui:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())


def stop(context):
    try:
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        ctrl = panel.controls.itemById(CMD_ID) if panel else None
        if ctrl:
            ctrl.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        _live_state['inputs'] = None
        try:
            _app.unregisterCustomEvent(LIVE_EVENT)
        except Exception:
            pass
        _handlers.clear()
    except Exception:
        if _ui:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())
