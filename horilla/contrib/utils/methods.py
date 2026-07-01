"""
Utility methods for the Horilla application.

This module contains helper functions that provide additional
functionality for working with models and other components in the
Horilla application.
"""

# Standard library imports
import logging
import re

# Third-party imports
import bleach
from bleach.css_sanitizer import CSSSanitizer
from django import template
from django.middleware.csrf import get_token
from django.template import loader
from django.template.defaultfilters import register
from django.utils.functional import lazy
from django.utils.html import format_html

# Third-party imports (Django)
from django.utils.safestring import SafeString

from horilla import settings

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType
from horilla.menu.sub_section_menu import sub_section_menu as menu_registry

# Local imports
from .middlewares import _thread_local

logger = logging.getLogger(__name__)


def get_horilla_model_class(app_label, model):
    """
    Retrieves the model class for the given app label and model
    name using Django's HorillaContentType framework.
    Args:
        app_label (str): The label of the application where the model is defined.
        model (str): The name of the model to retrieve.

    Returns:
        Model: The Django model class corresponding to the specified app label and model name.

    """
    content_type = HorillaContentType.objects.get(app_label=app_label, model=model)
    model_class = content_type.model_class()
    return model_class


def csrf_input(request):
    """Return an HTML snippet for the CSRF hidden input for the given request."""
    return format_html(
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">',
        get_token(request),
    )


@register.simple_tag(takes_context=True)
def csrf_token(context):
    """Access CSRF token inside the render_template method.

    Falls back to thread-local request if context does not contain a request.
    """
    try:
        request = context["request"]
    except Exception:
        request = getattr(_thread_local, "request")
    csrf_input_lazy = lazy(csrf_input, SafeString, str)
    return csrf_input_lazy(request)


def get_all_context_variables(request) -> dict:
    """
    This method will return dictionary format of context processors
    """
    if getattr(request, "all_context_variables", None) is None:
        all_context_variables = {}
        for processor_path in settings.TEMPLATES[0]["OPTIONS"]["context_processors"]:
            module_path, func_name = processor_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)
            context = func(request)
            all_context_variables.update(context)
        all_context_variables["csrf_token"] = csrf_token(all_context_variables)
        request.all_context_variables = all_context_variables
    return request.all_context_variables


def render_template(
    path: str,
    context: dict,
    decoding: str = "utf-8",
    status: int = None,
    _using=None,
) -> str:
    """
    This method is used to render HTML text with context.
    """
    request = getattr(_thread_local, "request", None)
    context.update(get_all_context_variables(request))
    template_loader = loader.get_template(path)
    template_body = template_loader.template.source
    template_bdy = template.Template(template_body)
    context_instance = template.Context(context)
    rendered_content = template_bdy.render(context_instance)
    return format_html("{}", rendered_content)


def closest_numbers(numbers: list, input_number: int) -> tuple:
    """
    This method is used to find previous and next of numbers
    """
    previous_number = input_number
    next_number = input_number
    try:
        index = numbers.index(input_number)
        if index > 0:
            previous_number = numbers[index - 1]
        else:
            previous_number = numbers[-1]
        if index + 1 == len(numbers):
            next_number = numbers[0]
        elif index < len(numbers):
            next_number = numbers[index + 1]
        else:
            next_number = numbers[0]
    except ValueError:
        # input_number not found in numbers; return defaults
        pass
    return (previous_number, next_number)


def get_section_info_for_model(model_input):
    """Fetch section and URL for a model's app from registered sub-section menus.

    Args:
        model_input: Either a model class or a string in
        format 'app_label.ModelName' or just 'ModelName'
    """

    # Convert string to model class if needed
    if isinstance(model_input, str):
        try:
            # Check if it's in 'app_label.ModelName' format
            if "." in model_input:
                model_class = apps.get_model(model_input)
            else:
                # If just model name, search across all apps
                model_class = None
                for app_config in apps.get_app_configs():
                    try:
                        model_class = app_config.get_model(model_input)
                        break
                    except LookupError:
                        continue

                if model_class is None:
                    logger.warning("Could not find model '%s' in any app", model_input)
                    return {"section": "", "url": "#"}

        except (LookupError, ValueError) as e:
            logger.warning("Could not get model from string '%s': %s", model_input, e)
            return {"section": "", "url": "#"}
    else:
        model_class = model_input

    # Now we always have a model class
    try:
        app_label = model_class._meta.app_label
    except AttributeError:
        logger.warning("Invalid model_input type: %s", type(model_input))
        return {"section": "", "url": "#"}

    try:
        if not isinstance(menu_registry, list):
            logger.warning("sub_section_menu is not a list: %s", type(menu_registry))
            return {"section": "", "url": "#"}

        for menu_cls in menu_registry:
            if hasattr(menu_cls, "app_label"):
                cls_app_label = getattr(menu_cls, "app_label", None)

                if cls_app_label == app_label:
                    return {
                        "section": getattr(menu_cls, "section", ""),
                        "url": str(getattr(menu_cls, "url", "")),
                    }

    except Exception as e:
        logger.warning("Error in get_section_info_for_model: %s", e)

    return {"section": "", "url": "#"}


# Allowlist used by sanitize_html — shared with mail preview and any other HTML-clean callsite.
HTML_ALLOWED_TAGS = [
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "caption",
    "cite",
    "code",
    "col",
    "colgroup",
    "dd",
    "del",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "font",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "ins",
    "kbd",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
]
HTML_ALLOWED_ATTRS = {
    "*": ["class", "id", "style"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "font": ["color", "face", "size"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
    "col": ["span"],
    "colgroup": ["span"],
}

# Only visual/layout CSS properties — no expression(), url(), or behaviour.
_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        # Color
        "color",
        "background-color",
        "background",
        # Font — both individual properties and the shorthand Summernote emits
        "font",
        "font-size",
        "font-weight",
        "font-style",
        "font-family",
        "font-variant",
        # Text
        "text-align",
        "text-decoration",
        "text-transform",
        "text-indent",
        "line-height",
        "letter-spacing",
        "word-spacing",
        "white-space",
        # Box model
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        # Border
        "border",
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "border-color",
        "border-width",
        "border-style",
        "border-radius",
        "border-collapse",
        "border-spacing",
        # Sizing
        "width",
        "height",
        "max-width",
        "max-height",
        "min-width",
        "min-height",
        # Layout
        "display",
        "vertical-align",
        "float",
        "clear",
        "overflow",
        # List
        "list-style",
        "list-style-type",
    ]
)

# Dangerous CSS value patterns that bypass the property allowlist.
# expression() is a legacy IE vector; url() can load external scripts via background.
_CSS_DANGEROUS_VALUE = re.compile(r"expression\s*\(|url\s*\(", re.IGNORECASE)


def _safe_style_attr(tag, name, value):
    """Attribute callback: drop style values containing dangerous CSS functions."""
    if name == "style" and _CSS_DANGEROUS_VALUE.search(value):
        return False
    return True


# Summernote's codeview emits <style> tags — keep the tag but wipe its content
# so page-level CSS injection is impossible while the tag round-trips cleanly.
_STYLE_TAG_CONTENT = re.compile(
    r"(<style[^>]*>)(.*?)(</style>)", re.IGNORECASE | re.DOTALL
)


def sanitize_html(value: str) -> str:
    """
    Strip disallowed tags and attributes from HTML using an allowlist.

    Safe for storing rich-text fields (mail body, notification message, etc.).
    Returns a clean string — dangerous tags are removed, not escaped.
    Non-string input is returned unchanged.
    """
    if not isinstance(value, str):
        return value

    # Blank out <style> tag content before bleach runs so CSS rules can't leak.
    value = _STYLE_TAG_CONTENT.sub(r"\1\3", value)

    def _allowed_attrs(tag, name, val):
        allowed = HTML_ALLOWED_ATTRS.get(tag, []) + HTML_ALLOWED_ATTRS.get("*", [])
        if name not in allowed:
            return False
        return _safe_style_attr(tag, name, val)

    return bleach.clean(
        value,
        tags=HTML_ALLOWED_TAGS + ["style"],
        attributes=_allowed_attrs,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )


def sanitize_plain_text(value: str) -> str:
    """
    Strip ALL HTML tags from a plain-text field (subject lines, URLs, titles).

    Use this for fields that should never contain markup at all.
    Non-string input is returned unchanged.
    """
    if not isinstance(value, str):
        return value
    return bleach.clean(value, tags=[], attributes={}, strip=True)


_PLAIN_TEXT_DANGER = re.compile(r"javascript\s*:", re.IGNORECASE)


def has_xss(value: str) -> bool:
    """
    Return True if ``value`` contains HTML markup or a javascript: pseudo-protocol.

    Kept for backwards compatibility with callers that use detect-and-reject logic
    on plain-text fields (URL fields, etc.).  Prefer ``sanitize_html`` /
    ``sanitize_plain_text`` for new code — they remove content rather than just detecting it.
    """
    if not isinstance(value, str):
        return False
    return bleach.clean(value, tags=[], attributes={}, strip=True) != value or bool(
        _PLAIN_TEXT_DANGER.search(value)
    )


def has_ssti(value: str) -> bool:
    """
    Detect dangerous Django template injection attempts in a string.

    Allows legitimate mail-merge variables like {{ instance.email }},
    {{ user.first_name }}, {{ active_company.name }}.

    Blocks access to sensitive context objects: request, settings,
    password fields, META, environ, and dangerous template tags
    (debug, load, include, extends, blocktranslate).

    Args:
        value (str): The string to check for SSTI patterns.

    Returns:
        bool: True if dangerous template patterns are detected, False otherwise.
    """
    if not isinstance(value, str):
        return False

    dangerous_patterns = [
        # settings object - always dangerous
        r"\{\{[\s\w|.\"']*\bsettings\b",
        # Dangerous paths on request object
        r"\brequest\s*\.\s*META\b",
        r"\brequest\s*\.\s*session\b",
        r"\brequest\s*\.\s*COOKIES\b",
        r"\brequest\s*\.\s*environ\b",
        # Password / secret field access anywhere in a variable chain
        r"\{\{[^}]*\bpassword\b[^}]*\}\}",
        r"\{\{[^}]*\bsecret\b[^}]*\}\}",
        r"\{\{[^}]*\bapi_key\b[^}]*\}\}",
        # Dangerous template tags
        r"\{%\s*debug\b",
        r"\{%\s*load\b",
        r"\{%\s*include\b",
        r"\{%\s*extends\b",
    ]

    combined = re.compile("|".join(dangerous_patterns), re.IGNORECASE | re.DOTALL)
    return bool(combined.search(value))
