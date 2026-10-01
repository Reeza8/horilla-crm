"""
History tab datetime formatter registry.

The History tab renders record timestamps and date/datetime diff values
through the ``history_datetime`` template filter. By default that filter uses
the user/company datetime format. Apps that need a different display (for
example another calendar system) register a formatter here instead of the
core filter importing them.

A formatter is a callable::

    def formatter(value, *, user=None, company=None):
        ...

``value`` is what the template passed to the filter: a ``date``, a
``datetime``, or the display string auditlog stored for a diff value. Return
the formatted text to use it, or ``None`` to leave the value to the next
formatter and finally to the default format.
"""

from typing import Callable, List, Optional, Tuple

HistoryDatetimeFormatter = Callable[..., Optional[str]]

# (priority, formatter), kept sorted by ascending priority
HISTORY_DATETIME_FORMATTERS: List[Tuple[int, HistoryDatetimeFormatter]] = []


def register_history_datetime_formatter(
    formatter: HistoryDatetimeFormatter, priority: int = 50
) -> HistoryDatetimeFormatter:
    """
    Register a formatter for the History tab's ``history_datetime`` filter.

    Lower ``priority`` values are tried first. Registering the same
    formatter again is a no-op. Returns ``formatter`` unchanged.
    """
    if any(registered is formatter for _, registered in HISTORY_DATETIME_FORMATTERS):
        return formatter
    HISTORY_DATETIME_FORMATTERS.append((priority, formatter))
    HISTORY_DATETIME_FORMATTERS.sort(key=lambda item: item[0])
    return formatter


def unregister_history_datetime_formatter(formatter: HistoryDatetimeFormatter):
    """Remove a formatter added with ``register_history_datetime_formatter``."""
    HISTORY_DATETIME_FORMATTERS[:] = [
        item for item in HISTORY_DATETIME_FORMATTERS if item[1] is not formatter
    ]


def get_history_datetime_formatters() -> List[HistoryDatetimeFormatter]:
    """Return the registered formatters in the order they are tried."""
    return [formatter for _, formatter in HISTORY_DATETIME_FORMATTERS]
