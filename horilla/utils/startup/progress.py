"""
Terminal startup progress bar for ``manage.py runserver``.

Shows progress while Django populates installed apps (import → models → ready).
Renders once per process; ignores later ``django.setup()`` / system-check calls.
"""

from __future__ import annotations

import os
import sys

_installed = False
_state = None

_STREAM = sys.stderr
_LINE_WIDTH = 96


def _should_enable() -> bool:
    """Enable only for the runserver process that actually serves requests."""
    if "runserver" not in sys.argv:
        return False
    if "--noreload" in sys.argv:
        return True
    return os.environ.get("RUN_MAIN") == "true"


def _bar(done: int, total: int, width: int = 30) -> str:
    total = max(total, 1)
    filled = min(width, int(width * done / total))
    return "#" * filled + "-" * (width - filled)


def _label_of(app_config) -> str:
    label = getattr(app_config, "label", None) or getattr(app_config, "name", "app")
    return str(label)[:28]


def _ensure_state(total_apps: int | None = None) -> dict:
    global _state
    if _state is None:
        if total_apps is None:
            try:
                from django.conf import settings

                total_apps = len(settings.INSTALLED_APPS)
            except Exception:
                total_apps = 1
        _state = {
            "total_apps": max(total_apps, 1),
            "done": 0,
            "finished": False,
            "started": False,
        }
    return _state


def _format_line(done: int, total: int, detail: str) -> str:
    pct = int(done * 100 / total) if total else 0
    return (
        f"Horilla loading [{_bar(done, total)}] "
        f"{pct:3d}% ({done}/{total}) {detail:<34}"
    )


def _write_inline(text: str) -> None:
    """Overwrite a single terminal line in place."""
    padded = text.ljust(_LINE_WIDTH)
    _STREAM.write("\r" + padded)
    _STREAM.flush()


def _render(app_config=None, phase: str = "", *, force: bool = False) -> None:
    if not _should_enable():
        return

    state = _ensure_state()
    if state["finished"] and not force:
        return

    total = state["total_apps"] * 3
    done = min(state["done"], total)

    if app_config is not None:
        if done >= total:
            detail = phase or "ready"
        else:
            detail = f"{phase} {_label_of(app_config)}".strip()
    else:
        detail = phase or "starting"
    detail = detail[:34]
    line = _format_line(done, total, detail)

    try:
        _write_inline(line)
    except Exception:
        return

    if done >= total and not state["finished"]:
        state["finished"] = True
        try:
            _STREAM.write("\nHorilla apps ready.\n")
            _STREAM.flush()
        except Exception:
            pass


def _tick(app_config=None, phase: str = "") -> None:
    if not _should_enable():
        return
    state = _ensure_state()
    if state["finished"]:
        return
    state["done"] += 1
    _render(app_config, phase=phase)


def announce_start() -> None:
    """Print the 0% line once, when app population actually begins."""
    if not _should_enable():
        return
    state = _ensure_state()
    if state["finished"] or state["started"]:
        return
    state["started"] = True
    _render(phase="starting", force=True)


def install() -> None:
    """
    Patch Django app loading so progress updates during import, models, and ready.

    Must run before Django populates the app registry (e.g. from ``manage.py``).
    """
    global _installed, _state

    if _installed:
        return

    if "runserver" not in sys.argv:
        return

    if not _should_enable():
        try:
            _STREAM.write(
                "Horilla runserver starting "
                "(loading Django, progress bar follows)...\n"
            )
            _STREAM.flush()
        except Exception:
            pass
        return

    _installed = True
    _state = None

    from django.apps.config import AppConfig
    from django.apps.registry import Apps

    original_init = AppConfig.__init__
    original_import_models = AppConfig.import_models
    original_populate = Apps.populate

    def __init__(self, app_name, app_module):
        original_init(self, app_name, app_module)
        _tick(self, phase="import")
        original_ready = self.ready

        def ready_with_progress(*args, **kwargs):
            try:
                return original_ready(*args, **kwargs)
            finally:
                _tick(self, phase="ready")

        self.ready = ready_with_progress

    def import_models(self):
        try:
            return original_import_models(self)
        finally:
            _tick(self, phase="models")

    def populate(self, installed_apps=None):
        if not getattr(self, "ready", False):
            announce_start()
        return original_populate(self, installed_apps)

    AppConfig.__init__ = __init__
    AppConfig.import_models = import_models
    Apps.populate = populate
