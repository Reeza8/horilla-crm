"""
Replace only the runserver ``Django version …`` banner line with Horilla's version.

Installed from ``manage.py`` — no extra INSTALLED_APPS entry required.
"""

from __future__ import annotations

_installed = False


def install() -> None:
    """Patch Daphne runserver to show ``Horilla version`` from ``horilla.__version__``."""
    global _installed
    if _installed:
        return
    _installed = True

    from daphne.management.commands.runserver import Command as DaphneCommand

    from horilla.__version__ import __version__ as HORILLA_VERSION

    original_inner_run = DaphneCommand.inner_run

    def get_version(self):
        return HORILLA_VERSION

    def inner_run(self, *args, **options):
        original_write = self.stdout.write

        def write(msg="", *a, **kw):
            if isinstance(msg, str) and msg.startswith("Django version "):
                msg = "Horilla version " + msg[len("Django version ") :]
            return original_write(msg, *a, **kw)

        self.stdout.write = write
        try:
            return original_inner_run(self, *args, **options)
        finally:
            self.stdout.write = original_write

    DaphneCommand.get_version = get_version
    DaphneCommand.inner_run = inner_run
