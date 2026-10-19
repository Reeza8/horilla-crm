"""
Phone search: text and phone-number matching that copes with how people type
on a phone (Persian or Arabic digits and letters, spaces and dashes).
"""

# Standard library imports
import re

# Third-party imports (Django)
from django.db.models.functions import Replace

# First party imports (Horilla)
from horilla.db.models import Q, Value

# Search only starts at this many characters.
MIN_QUERY_LENGTH = 2

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_TO_LATIN_DIGITS = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, "0123456789" * 2)
_TO_PERSIAN_DIGITS = str.maketrans("0123456789", PERSIAN_DIGITS)

# Arabic letters Persian keyboards differ on, and their Persian form.
_ARABIC_TO_PERSIAN_LETTERS = str.maketrans("يك", "یک")
_PERSIAN_TO_ARABIC_LETTERS = str.maketrans("یک", "يك")

# Characters ignored when matching phone numbers. LRM/RLM/ZWNJ come from
# copying a number out of right-to-left text.
PHONE_SEPARATORS = (" ", "-", "(", ")", ".", "‌", "‎", "‏")
_PHONE_SEPARATORS_RE = re.compile("[" + re.escape("".join(PHONE_SEPARATORS)) + "]")


def to_latin_digits(text):
    """Replace Persian and Arabic digits in ``text`` with 0-9."""
    return (text or "").translate(_TO_LATIN_DIGITS)


def phone_digits(text):
    """
    Return the digits of a typed phone number, or "" when ``text`` isn't one.

    ``"۰۹۱۲ ۳۴۵-۶۷۸۹"`` and ``"+98 912 345 6789"`` both count; letters don't.
    """
    cleaned = _PHONE_SEPARATORS_RE.sub("", to_latin_digits(text).strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned if cleaned.isdigit() else ""


def tel_href(number):
    """Return a ``tel:`` value: Latin digits, an optional leading +, no spacing."""
    cleaned = _PHONE_SEPARATORS_RE.sub("", to_latin_digits(str(number or "")).strip())
    plus = "+" if cleaned.startswith("+") else ""
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    return f"{plus}{digits}" if digits else ""


def text_variants(query):
    """
    Return the spellings to look for: the query as typed, with Latin digits,
    and with Persian/Arabic forms of ``ی`` and ``ک`` swapped.
    """
    variants = {
        query,
        to_latin_digits(query),
        query.translate(_ARABIC_TO_PERSIAN_LETTERS),
        query.translate(_PERSIAN_TO_ARABIC_LETTERS),
    }
    return [variant for variant in variants if variant]


def _stripped(field_name):
    """Expression for ``field_name`` with the phone separators removed."""
    expression = field_name
    for separator in PHONE_SEPARATORS:
        expression = Replace(expression, Value(separator), Value(""))
    return expression


def apply_search(queryset, config, query):
    """
    Filter ``queryset`` (of ``config.model``) by ``query``.

    Text is matched (case-insensitively) against the title, email and
    ``search_fields``. When the query is a phone number it is also matched
    against ``phone_fields`` with separators ignored, whether the stored number
    uses Latin or Persian digits.
    """
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        return queryset

    text_fields = []
    for name in (config.title_field, config.email_field, *config.search_fields):
        if name and name not in text_fields:
            text_fields.append(name)
    condition = Q()
    for variant in text_variants(query):
        for name in text_fields:
            condition |= Q(**{f"{name}__icontains": variant})

    digits = phone_digits(query)
    if digits and config.phone_fields:
        annotations = {}
        for index, name in enumerate(config.phone_fields):
            alias = f"_mobile_phone_{index}"
            annotations[alias] = _stripped(name)
            condition |= Q(**{f"{alias}__contains": digits})
            condition |= Q(
                **{f"{alias}__contains": digits.translate(_TO_PERSIAN_DIGITS)}
            )
        queryset = queryset.alias(**annotations)

    return queryset.filter(condition)
