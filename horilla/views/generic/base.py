"""Base view class for all Horilla views."""

from functools import update_wrapper

from django.core.exceptions import FieldDoesNotExist
from django.views.generic import TemplateView as DjangoTemplateView
from django.views.generic import View as DjangoView


class View(DjangoView):
    """
    Base view class for all Horilla views.

    ``as_view`` resolves ``_inherit_view`` extensions for the concrete subclass
    on each request (same late-binding idea as list/card/kanban composition).
    """

    @classmethod
    def as_view(cls, **initkwargs):
        """Return a callable that resolves ``_inherit_view`` extensions per request."""
        if getattr(cls, "__horilla_view_composed__", False):
            return super().as_view(**initkwargs)

        base_view = super().as_view(**initkwargs)

        def view(request, *args, **kwargs):
            from horilla.extension.view.resolve import resolve_view_class

            resolved = resolve_view_class(cls)
            if resolved is not cls:
                if (
                    getattr(view, "_extended_handler", None) is None
                    or getattr(view, "_extended_cls", None) is not resolved
                ):
                    view._extended_cls = resolved
                    view._extended_handler = resolved.as_view(**initkwargs)
                return view._extended_handler(request, *args, **kwargs)
            return base_view(request, *args, **kwargs)

        update_wrapper(view, base_view)
        view.view_class = cls
        view.view_initkwargs = initkwargs
        return view


class TemplateView(DjangoTemplateView):
    """
    Base view class for all Horilla template views.
    """

    body: list = []
    fieldsets = ()
    header_fields: list = []
    model = None

    def _normalize_field_list(self, field_list):
        """Normalize fields to ``(verbose_name, field_name)`` tuples."""
        if not field_list:
            return []
        model = getattr(self, "model", None)
        result = []
        for field in field_list:
            if isinstance(field, (list, tuple)) and len(field) >= 2:
                field_name = field[1]
                label = field[0]
            else:
                field_name = field
                label = field
            if model:
                try:
                    model_field = model._meta.get_field(field_name)
                    result.append((model_field.verbose_name, field_name))
                    continue
                except FieldDoesNotExist:
                    pass
            result.append((label, field_name))
        return result

    def get_fieldsets(self):
        """
        Return fieldsets as dicts with ``(verbose_name, field_name)`` lists.

        When ``fieldsets`` is empty, falls back to a single untitled group
        from ``body`` (excluding the first entry when it is used as title).
        """
        declared = getattr(self, "fieldsets", None) or ()
        if not declared:
            body = getattr(self, "body", None) or []
            if not body:
                return []
            grid = (
                body[1:]
                if len(body) > 1 and not getattr(self, "header_fields", None)
                else body
            )
            fields = self._normalize_field_list(grid)
            return (
                [{"name": "", "fields": fields, "description": None, "icon": None}]
                if fields
                else []
            )

        result = []
        for name, options in declared:
            fields = self._normalize_field_list(options.get("fields", ()))
            if fields:
                result.append(
                    {
                        "name": name,
                        "fields": fields,
                        "description": options.get("description"),
                        "icon": options.get("icon"),
                    }
                )
        return result

    def get_context_data(self, **kwargs):
        """Add fieldsets to the template context."""
        context = super().get_context_data(**kwargs)
        context["fieldsets"] = self.get_fieldsets()
        return context
