"""Base view class for all Horilla views."""

from functools import update_wrapper

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
