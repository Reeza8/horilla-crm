"""Reusable component tags (inclusion tags) for Horilla templates."""

from inspect import getfullargspec

from django.template.base import Node
from django.template.library import parse_bits
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from ._registry import register

# Written out in full so the classes stay greppable.
SPINNER_SIZES = {
    "xs": "h-3 w-3",
    "sm": "h-5 w-5",
    "md": "h-6 w-6",
    "lg": "h-8 w-8",
}


@register.inclusion_tag("components/_reload_button.html", takes_context=True)
def reload_button(
    context,
    container,
    *,
    swap="outerHTML",
    url=None,
    trigger="click",
    label="click",
    indicator=None,
    button_id="reloadButton",
    hidden=True,
    **attrs,
):
    """
    Render a hidden HTMX button that refreshes ``container`` (a CSS selector).

    The button re-fetches the current page and replaces ``container`` with the same
    element taken from the response, so ``container`` is used for both ``hx-target``
    and ``hx-select``. Any other ``hx-*`` attribute is passed as a keyword with
    underscores (``hx_push_url="true"``, ``hx_select_oob="#dropdown-companies"``).
    A keyword whose name matches a generated attribute replaces it, so a different
    ``hx-select`` is ``hx_select="#other"`` and ``hx_select=""`` leaves it out.
    """

    if url is None:
        request = context.get("request")
        if request:
            query = request.GET.urlencode()
            url = f"{request.path}?{query}" if query else request.path
        else:
            url = ""

    pairs = {
        "hx-get": url,
        "hx-target": container,
        "hx-trigger": trigger,
        "hx-swap": swap,
        "hx-select": container,
        "hx-indicator": indicator,
    }

    # Custom attributes override defaults instead of creating duplicates.
    pairs.update((name.replace("_", "-"), value) for name, value in attrs.items())

    rendered = []
    for name, value in pairs.items():
        if value is None or value is False or value == "":
            continue

        rendered.append((name, None if value is True else value))

    return {
        "button_id": button_id,
        "hidden": hidden,
        "label": label,
        "attrs": rendered,
    }


@register.inclusion_tag("components/_modal_header.html")
def modal_header(title, on_close="closeModal()", button_id="", badge=None):
    """Render the standard modal header: title on the left, close button on the right.

    Usage:
        {% modal_header _("Account Hierarchy") %}
        {% modal_header _("Insert Fields") on_close="closeContentModal()" %}
    """
    return {
        "title": title,
        "on_close": on_close,
        "button_id": button_id,
        "badge": badge,
    }


@register.inclusion_tag("components/_spinner.html")
def spinner(size="lg", *, centered=False, wrapper_class=""):
    """Render the animated loading ring in the theme's primary colour.

    ``size`` is one of ``xs`` (h-3), ``sm`` (h-5), ``md`` (h-6) or ``lg`` (h-8,
    the default). ``centered=True`` wraps the ring in a
    ``flex justify-center items-center p-4`` block, the usual body of an
    ``.htmx-indicator``; ``wrapper_class`` adds classes to that block (e.g.
    ``"w-full"``). The outer element itself (``htmx-indicator``, ids, ``<li>``
    with hx-* attributes) differs per call site and stays in the template.

    Usage:
        {% spinner %}
        {% spinner "sm" %}
        {% spinner centered=True %}
    """
    if size not in SPINNER_SIZES:
        raise ValueError(
            f"Unknown spinner size {size!r}; expected one of {', '.join(SPINNER_SIZES)}"
        )
    return {
        "size_class": SPINNER_SIZES[size],
        "centered": centered,
        "wrapper_class": wrapper_class,
    }


BTN_VARIANTS = {
    "primary": (
        "bg-primary-600 rounded-md hover:bg-primary-800 transition duration-300 "
        "text-white"
    ),
    "outline": (
        "outline outline-1 outline-offset-[-1px] outline-primary-600 rounded-md "
        "hover:bg-primary-300 transition duration-300 text-primary-600"
    ),
}
BTN_TAGS = ("button", "a", "span", "label")


def btn(
    label=None,
    *,
    variant="primary",
    sizing="text-sm px-4 py-2",
    extra_class="",
    tag="button",
    loading_id="",
    **attrs,
):
    """Render a themed button with the shared primary or outline colour tokens.

    The tag owns the colour tokens; ``sizing`` carries text size, padding and width
    (default ``text-sm px-4 py-2``) and ``extra_class`` any other class or JS hook.
    Other keywords become attributes with underscores turned into dashes
    (``hx_get`` is ``hx-get``, ``hx_on__after_request`` is
    ``hx-on--after-request``). ``True`` renders a bare attribute; ``None``, ``False``
    and ``""`` leave it out. ``tag`` is ``button`` (default), ``a``, ``span`` or
    ``label``. ``label`` defaults to "Save" for ``type="submit"``; any other type
    needs one, unless ``body`` is set and the contents are between ``{% endbtn %}``.

    ``loading_id`` puts the HTMX spinner image inside the button, before the label,
    in a ``htmx-indicator`` span with that id; point ``hx_indicator`` at it.
    ``body`` switches on ``{% endbtn %}`` so the template can place an icon or
    other markup inside the control. Without ``body`` there is no closing tag.

    Usage:
        {% btn type="submit" %}
        {% btn type="submit" hx_indicator="#single-form-save-spinner" loading_id="single-form-save-spinner" %}
        {% btn body type="submit" sizing="p-3 w-full" extra_class="flex gap-3 justify-center" %}
            <img src="..." alt="">
            {% trans "Sign In" %}
        {% endbtn %}
    """
    if variant not in BTN_VARIANTS:
        raise ValueError(
            f"Unknown btn variant {variant!r}; expected one of {', '.join(BTN_VARIANTS)}"
        )
    if tag not in BTN_TAGS:
        raise ValueError(
            f"Unknown btn tag {tag!r}; expected one of {', '.join(BTN_TAGS)}"
        )
    has_body = attrs.pop("has_body", False)
    if label is None and not has_body:
        if attrs.get("type") != "submit":
            raise ValueError('btn needs a label unless type="submit"')
        label = _("Save")

    classes = " ".join(
        part for part in (BTN_VARIANTS[variant], sizing, extra_class) if part
    )
    rendered = []
    for name, value in attrs.items():
        if value is None or value is False or value == "":
            continue
        rendered.append((name.replace("_", "-"), None if value is True else value))

    return {
        "tag": tag,
        "label": label,
        "classes": classes,
        "attrs": rendered,
        "loading_id": loading_id,
        "body": "",
    }


class BtnNode(Node):
    """Renders ``{% btn %}``. With ``body``, the nodelist is the inner HTML."""

    def __init__(self, args, kwargs, nodelist):
        self.args = args
        self.kwargs = kwargs
        self.nodelist = nodelist

    def render(self, context):
        resolved_args = [arg.resolve(context) for arg in self.args]
        resolved_kwargs = {
            key: value.resolve(context) for key, value in self.kwargs.items()
        }
        if self.nodelist is not None:
            resolved_kwargs["has_body"] = True
        data = btn(*resolved_args, **resolved_kwargs)
        if self.nodelist is not None:
            data["body"] = mark_safe(self.nodelist.render(context))
            data["loading_id"] = ""

        return get_template("components/_btn.html").render(data)


@register.tag("btn")
def compile_btn(parser, token):
    """Compile ``{% btn %}``. ``body`` is the only signal that ``{% endbtn %}`` follows."""
    bits = token.split_contents()[1:]
    has_body = "body" in bits
    bits = [bit for bit in bits if bit != "body"]
    spec = getfullargspec(btn)
    args, kwargs = parse_bits(
        parser,
        bits,
        spec.args,
        spec.varargs,
        spec.varkw,
        spec.defaults,
        spec.kwonlyargs,
        spec.kwonlydefaults,
        "btn",
    )
    nodelist = None
    if has_body:
        nodelist = parser.parse(("endbtn",))
        parser.delete_first_token()

    return BtnNode(args, kwargs, nodelist)
