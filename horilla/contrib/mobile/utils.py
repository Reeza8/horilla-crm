"""
Helpers shared by the mobile views, templates and service worker.
"""

# Standard library imports
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

# First party imports (Horilla)
from horilla.__version__ import __version__ as PLATFORM_VERSION
from horilla.utils.translation import get_language

from .__version__ import __version__ as MOBILE_VERSION

# Page name the mobile layout passes to ``load_registered_html``. Other apps
# can inject head/body fragments into the phone layout with
# ``register_html(..., page=MOBILE_PAGE)``.
MOBILE_PAGE = "mobile"

# Prefix of every cache the service worker creates, so it can delete the
# caches of older versions without touching anything else on the origin.
CACHE_PREFIX = "horilla-mobile-"


# This app's own static files (mobile.css, mobile.js).
STATIC_DIR = Path(__file__).resolve().parent / "static"


@lru_cache(maxsize=1)
def _own_static_digest():
    """Short hash of the names and contents of this app's static files."""
    digest = sha256()
    for path in sorted(STATIC_DIR.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(STATIC_DIR).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


def get_asset_version():
    """
    Return the version stamp added to static URLs on mobile pages.

    The service worker only caches static files whose ``v`` query parameter
    equals this stamp. It changes with every platform or mobile release, and
    whenever this app's own static files change, so a deploy gets a new cache
    instead of serving the previous files.
    """
    return f"{PLATFORM_VERSION}-{MOBILE_VERSION}-{_own_static_digest()}"


def user_display_name(user):
    """
    A user's full name, or their username when they have none. Anything that
    isn't a user (an owner field can point elsewhere) is shown as ``str()``.
    """
    if hasattr(user, "get_full_name") and hasattr(user, "get_username"):
        return user.get_full_name() or user.get_username()
    return str(user)


# Digits of the languages that don't write numbers with Latin digits.
_NATIVE_DIGITS = {
    "fa": str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"),
    "ar": str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"),
}


def local_digits(value):
    """``value`` as text, in the active language's own digits (Persian, Arabic)."""
    table = _NATIVE_DIGITS.get((get_language() or "").split("-")[0])
    text = str(value)
    return text.translate(table) if table else text
