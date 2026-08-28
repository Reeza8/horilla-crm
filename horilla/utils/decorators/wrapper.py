"""
Custom decorators used across Horilla for permission handling,
HTMX validation, and database initialization checks.
"""

# Standard library imports
from functools import wraps

from django.conf import settings
from django.http import HttpResponse

# Third-party imports (Django)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

# First-party / Horilla imports
from horilla.web import safe_url


def permission_required_or_denied(
    perms,
    template_name="403.html",
    require_all=False,
    modal=False,
    embed=None,
    wrapper_id="",
):
    """
    Custom decorator for both FBVs and CBVs.
    - `perms`: single permission string or a list/tuple of permissions.
    - `require_all`: if True, user must have ALL permissions; if False, ANY one is enough.
    - `embed`: if True, render 403 as fragment for layout (e.g. #mainSession). If None,
      embed is auto when request is HTMX and not modal so swapped content fills the target.
    - `wrapper_id`: id to stamp on the embedded 403 fragment's outer div. Set this to the
      page's own view_id so a sidebar link's hx-select="#that-id" still finds something to
      swap in when the request is denied instead of leaving the target empty.
    """

    if isinstance(perms, str):
        perms = [perms]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):

            request = args[0] if hasattr(args[0], "user") else args[1]
            user = request.user

            if not user.is_authenticated:
                login_url = f"{reverse_lazy('core:login')}?next={request.path}"
                return redirect(login_url)
                # return render(request, "login.html")

            if require_all:
                has_permission = user.has_perms(perms)
            else:
                has_permission = user.has_any_perms(perms)

            if has_permission:
                return view_func(*args, **kwargs)
            context = {"permissions": perms, "modal": modal}
            # HTMX swaps into #mainSession etc.; full error.html breaks layout—use embed fragment.
            if not modal and (
                embed is True
                or (embed is not False and request.META.get("HTTP_HX_REQUEST"))
            ):
                context["embed"] = True
                # Sidebar links hx-select a page-specific id (e.g. #automation-view);
                # without it the embedded 403 fragment has nothing for htmx to swap in.
                if wrapper_id:
                    context["wrapper_id"] = wrapper_id
            return render(request, template_name, context)

        return _wrapped_view

    return decorator


def permission_required(perms, require_all=False):
    """
    Custom decorator for both FBVs and CBVs.
    Returns 403 if user doesn't have required permission(s).
    """
    if isinstance(perms, str):
        perms = [perms]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(*args, **kwargs):
            request = args[0] if hasattr(args[0], "user") else args[1]
            user = request.user

            if not user.is_authenticated:
                login_url = f"{reverse_lazy('core:login')}?next={request.path}"
                return redirect(login_url)

            if require_all:
                has_permission = user.has_perms(perms)
            else:
                has_permission = user.has_any_perms(perms)

            if has_permission:
                return view_func(*args, **kwargs)
            return HttpResponse("")

        return _wrapped_view

    return decorator


def htmx_required(view_func=None, login=True):
    """
    Ensure the request is an HTMX request.
    Optionally enforce authentication before allowing access.
    """

    def decorator(func):
        @wraps(func)
        def _wrapped_view(request, *args, **kwargs):
            if login and not request.user.is_authenticated:
                login_url = f"{reverse_lazy('core:login')}?next={request.path}"
                return redirect(login_url)
            if not request.headers.get("HX-Request") == "true":
                return render(request, "405.html")
            return func(request, *args, **kwargs)

        return _wrapped_view

    # If called without arguments: @htmx_required
    if view_func is not None:
        return decorator(view_func)

    # If called with arguments: @htmx_required(login=False)
    return decorator


def db_initialization(model=None):
    """
    Decorator factory.
    @method_decorator(db_initialization(model=User), name="dispatch")
    """

    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Does the database still need initialization?
            needs_initialization = not model.objects.exists()

            # 2. Is the correct password stored in session?
            correct_password = settings.DB_INIT_PASSWORD
            password_valid = request.session.get("db_password") == correct_password

            # If DB is already initialized OR password is wrong → redirect away
            if not needs_initialization or not password_valid:
                next_url = safe_url(request, request.GET.get("next", "/"))
                return redirect(next_url)

            # Otherwise allow the original view to run
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return actual_decorator
