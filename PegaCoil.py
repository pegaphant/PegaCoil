"""PegaCoil – Fusion-Add-in: Stator-Leiterplatte für einen PCB-Motor auslegen und zeichnen."""

import importlib
import os
import traceback

import adsk.core
import adsk.fusion

from . import pegacoil
from .pegacoil import design as _design, drc as _drc, kicad as _kicad, layout as _layout, report as _report

for _m in (_design, _layout, _drc, _kicad, _report, pegacoil):
    importlib.reload(_m)
from .pegacoil import fusion_draw  # noqa: E402

importlib.reload(fusion_draw)

CMD_ID = 'PegaCoil_Stator'
PANEL_ID = 'SolidScriptsAddinsPanel'
HERE = os.path.dirname(os.path.abspath(__file__))

_app = None
_ui = None
_handlers = []
_last = {'key': None, 'result': None}

LAYERS = [('Automatisch', 0), ('2', 2), ('4', 4), ('6', 6), ('8', 8)]
COILS = [('Automatisch', 0)] + [(str(c), c) for c in _design.COIL_CHOICES]
OUTER = [('Automatisch', 0.0), ('1 oz (35 µm)', 1.0), ('2 oz (70 µm)', 2.0)]
INNER = [('0,5 oz (17,5 µm)', 0.5), ('1 oz (35 µm)', 1.0)]


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
        max_rise=val('rise'),
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


def _show(inputs, text):
    box = inputs.itemById('result')
    box.formattedText = '<pre>' + text.replace('&', '&amp;').replace('<', '&lt;') + '</pre>'


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.setDialogInitialSize(560, 760)
            inputs = cmd.commandInputs
            inputs.addValueInput('od', 'Außendurchmesser', 'mm', adsk.core.ValueInput.createByString('60 mm'))
            inputs.addValueInput('id', 'Innendurchmesser', 'mm', adsk.core.ValueInput.createByString('10 mm'))
            inputs.addFloatSpinnerCommandInput('power', 'Leistung (W)', '', 0.1, 2000, 1, 10)
            inputs.addFloatSpinnerCommandInput('volt', 'Spannung (V)', '', 1, 400, 1, 12)
            _dropdown(inputs, 'layers', 'Lagen', LAYERS)
            _dropdown(inputs, 'coils', 'Spulen', COILS)
            _dropdown(inputs, 'outer_oz', 'Kupfer außen', OUTER)
            _dropdown(inputs, 'inner_oz', 'Kupfer innen', INNER)

            grp = inputs.addGroupCommandInput('adv', 'Erweitert')
            grp.isExpanded = False
            gi = grp.children
            gi.addFloatSpinnerCommandInput('b_gap', 'Flussdichte Luftspalt (T)', '', 0.05, 1.5, 0.05, 0.3)
            gi.addFloatSpinnerCommandInput('rise', 'Max. Erwärmung (K)', '', 5, 120, 5, 40)
            gi.addFloatSpinnerCommandInput('min_trace', 'Min. Bahnbreite mm (0 = auto)', '', 0, 2, 0.01, 0)
            gi.addFloatSpinnerCommandInput('min_space', 'Min. Abstand mm (0 = auto)', '', 0, 2, 0.01, 0)
            gi.addFloatSpinnerCommandInput('via_drill', 'Via-Bohrung (mm)', '', 0.15, 1, 0.05, 0.3)
            gi.addFloatSpinnerCommandInput('via_pad', 'Via-Pad (mm)', '', 0.3, 2, 0.05, 0.6)
            gi.addFloatSpinnerCommandInput('pad_drill', 'Anschluss-Bohrung (mm)', '', 0.5, 3, 0.1, 1.0)
            gi.addFloatSpinnerCommandInput('pad_d', 'Anschluss-Pad (mm)', '', 1, 5, 0.1, 2.0)

            inputs.addBoolValueInput('calc', 'Berechnen', False, '', False)
            inputs.addTextBoxCommandInput('result', 'Ergebnis', 'Werte eingeben und „Berechnen“ drücken.', 22, True)
            inputs.addBoolValueInput('draw', 'In Fusion zeichnen', True, '', True)
            inputs.addBoolValueInput('one_coil', 'Nur eine Spule zeichnen (schneller)', True, '', False)
            inputs.addBoolValueInput('body', 'Leiterplatte als Körper', True, '', True)
            inputs.addBoolValueInput('kicad', 'KiCad-Datei speichern', True, '', True)

            for h, ev in ((InputChangedHandler(), cmd.inputChanged), (ExecuteHandler(), cmd.execute)):
                ev.add(h)
                _handlers.append(h)
        except Exception:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        inp = args.input
        if inp.id != 'calc':
            return
        inputs = args.inputs
        try:
            _show(inputs, _compute(inputs)[2])
        except ValueError as e:
            _show(inputs, str(e))
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
                fusion_draw.draw(des, lay, inputs.itemById('one_coil').value, inputs.itemById('body').value)
        except Exception:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        old = _ui.commandDefinitions.itemById(CMD_ID)
        if old:
            old.deleteMe()
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, 'PegaCoil', 'Stator-Leiterplatte für einen PCB-Motor auslegen', os.path.join(HERE, 'resources')
        )
        h = CreatedHandler()
        cmd_def.commandCreated.add(h)
        _handlers.append(h)
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel and not panel.controls.itemById(CMD_ID):
            panel.controls.addCommand(cmd_def)
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
        _handlers.clear()
    except Exception:
        if _ui:
            _ui.messageBox('PegaCoil:\n' + traceback.format_exc())
