"""
Bootstrap all Horilla extension layers after Django has finished loading apps.

Called from ``horilla.urls.project`` (after ``apps.ready``) so extension apps
listed after their target apps in ``INSTALLED_APPS`` are included.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def bootstrap_extensions() -> None:
    """
    Compose form, filter, nav, list, card, kanban, detail, formatter, and view
    extensions, once the app registry is fully ready.
    """
    try:
        from django.apps import apps as django_apps

        if not django_apps.ready:
            return
    except Exception:
        return

    try:
        from horilla.extension.card.bootstrap import apply_card_extensions
        from horilla.extension.detail.bootstrap import apply_detail_extensions
        from horilla.extension.filter.bootstrap import apply_filter_extensions
        from horilla.extension.formatting.bootstrap import apply_formatter_extensions
        from horilla.extension.forms.bootstrap import apply_form_extensions
        from horilla.extension.kanban.bootstrap import apply_kanban_extensions
        from horilla.extension.list.bootstrap import apply_list_extensions
        from horilla.extension.nav.bootstrap import apply_nav_extensions
        from horilla.extension.view.bootstrap import apply_view_extensions

        apply_form_extensions(force=True)
        apply_filter_extensions(force=True)
        apply_nav_extensions(force=True)
        apply_list_extensions(force=True)
        apply_card_extensions(force=True)
        apply_kanban_extensions(force=True)
        apply_detail_extensions(force=True)
        apply_formatter_extensions(force=True)
        apply_view_extensions(force=True)
    except Exception as exc:
        logger.warning(
            "Horilla extension bootstrap failed: %s",
            exc,
            exc_info=True,
        )
