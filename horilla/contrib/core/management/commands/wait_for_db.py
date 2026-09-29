"""
Horilla management command that waits for the configured database to accept connections.

The Docker entrypoint runs this before ``migrate``. The host and port are read
from ``settings.DATABASES`` -- the same values Django connects with, whether
they came from ``DATABASE_URL`` or ``DB_HOST``/``DB_PORT`` -- so the database
does not have to be a Compose service named ``db``.
"""

# Standard library imports
import socket
import time

# Third-party imports (Django)
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Ports the database drivers fall back to when the settings leave PORT empty
# (e.g. a DATABASE_URL that names a host but no port).
DEFAULT_PORTS = {
    "postgresql": 5432,
    "postgis": 5432,
    "mysql": 3306,
}


def get_wait_target(config):
    """
    Return the (host, port) to probe for a DATABASES entry, or None when there
    is no TCP server to wait for (SQLite, a Unix socket, or an unknown engine
    with no port set).
    """
    host = config.get("HOST") or ""
    if not host or host.startswith("/"):
        return None

    port = config.get("PORT")
    if port:
        return host, int(port)

    engine = config.get("ENGINE", "")
    for name, default_port in DEFAULT_PORTS.items():
        if name in engine:
            return host, default_port
    return None


class Command(BaseCommand):
    """
    Django management command that blocks until the configured database
    accepts TCP connections, or fails after a fixed number of attempts.
    """

    help = "Waits until the configured database accepts TCP connections"

    # Runs before migrate, while the database may still be down; system checks
    # are not needed to read the connection settings.
    requires_system_checks = []

    def add_arguments(self, parser):
        """Add command-line arguments for the wait loop."""
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to wait for (default: default)",
        )
        parser.add_argument(
            "--attempts",
            type=int,
            default=30,
            help="Number of connection attempts before giving up (default: 30)",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds to sleep between attempts (default: 1)",
        )

    def handle(self, *args, **options):
        """Probe the database host and port until it answers or attempts run out."""
        alias = options["database"]
        if alias not in settings.DATABASES:
            raise CommandError(f"Unknown database alias: {alias}")

        target = get_wait_target(settings.DATABASES[alias])
        if target is None:
            self.stdout.write(
                "No database server host/port configured; skipping the wait."
            )
            return

        host, port = target
        attempts = options["attempts"]
        for attempt in range(1, attempts + 1):
            try:
                with socket.create_connection((host, port), timeout=5):
                    pass
            except OSError:
                if attempt < attempts:
                    time.sleep(options["interval"])
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Database is ready at {host}:{port}")
                )
                return

        raise CommandError(
            f"Database at {host}:{port} not available after {attempts} attempts"
        )
