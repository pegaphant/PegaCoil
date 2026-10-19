"""Selbst-Aktualisierung: das Add-in-Verzeichnis ist ein git-Klon von github.com/pegaphant/PegaCoil.

start() beim Fusion-Start: im Hintergrund 'git fetch' (ohne Fenster, ohne Anmelde-Dialog). Gibt es einen neuen
Stand und ist lokal nichts geändert, wird er sofort geholt (nur vorspulen – eigene Änderungen werden nie
überschrieben). status_text() für das Fenster, take_pulled() sagt dem Add-in, dass es neu laden soll.
"""

import os
import subprocess
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_state = {'done': False, 'pulled': False, 'files': [], 'behind': 0, 'ahead': 0, 'dirty': False, 'error': None}
_lock = threading.Lock()


def _git(*args, timeout=30):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    r = subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=timeout, env=env, creationflags=flags)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(msg[-1] if msg else 'git-Fehler')
    return r.stdout.strip()


def available():
    return os.path.exists(os.path.join(ROOT, '.git'))


def version():
    """Datum/Uhrzeit des letzten Commits wie PegaCAM: JJJJ.MM.TT.HHMM + Kurz-Hash ('+' = lokal geändert)."""
    if not available():
        return '?'
    try:
        v = _git('log', '-1', '--format=%cd %h', '--date=format:%Y.%m.%d.%H%M')
        if _git('status', '--porcelain', '--untracked-files=no'):
            v += '+'
        return v
    except Exception:
        return '?'


def check_and_pull():
    """Mit GitHub vergleichen und – wenn lokal nichts geändert ist – den neuen Stand holen."""
    if not available():
        with _lock:
            _state.update(done=True, error='kein git-Klon')
        return
    try:
        _git('fetch', '--quiet', 'origin', timeout=60)
        ahead, behind = (int(x) for x in _git('rev-list', '--left-right', '--count', 'HEAD...@{u}').split())
        dirty = bool(_git('status', '--porcelain', '--untracked-files=no'))
        pulled, files = False, []
        if behind and not ahead and not dirty:
            files = _git('diff', '--name-only', 'HEAD', '@{u}').splitlines()
            _git('merge', '--ff-only', '--quiet', '@{u}', timeout=60)
            pulled, behind = True, 0
        with _lock:
            _state.update(done=True, pulled=pulled, files=files, behind=behind, ahead=ahead, dirty=dirty, error=None)
    except Exception as e:
        with _lock:
            _state.update(done=True, error=str(e)[:200])


def start():
    threading.Thread(target=check_and_pull, daemon=True).start()


def take_pulled():
    """Liste der geänderten Dateien, wenn seit dem letzten Aufruf aktualisiert wurde (sonst leer)."""
    with _lock:
        if not _state['pulled']:
            return []
        _state['pulled'] = False
        return list(_state['files'])


def status_text():
    """Eine Zeile für das Fenster."""
    v = version()
    with _lock:
        st = dict(_state)
    if not available():
        return f'Version {v}'
    if not st['done']:
        return f'Version {v} – prüfe GitHub …'
    if st['error']:
        return f'Version {v} – GitHub nicht erreichbar'
    if st['behind'] and (st['dirty'] or st['ahead']):
        return f'Version {v} – <b>neue Version auf GitHub</b>, aber lokale Änderungen: nicht automatisch geholt'
    if st['ahead']:
        return f'Version {v} – {st["ahead"]} eigene Änderung(en) noch nicht hochgeladen'
    return f'Version {v} – aktuell'
