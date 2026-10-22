"""
Horilla text - re-exports django.utils.text for consistent imports.

Use: from horilla.utils.text import slugify
     from horilla.utils.text import Truncator, capfirst, ...
"""

from django.utils.text import (
    Truncator,
    camel_case_to_spaces,
    capfirst,
    compress_sequence,
    compress_string,
    get_text_list,
    get_valid_filename,
    normalize_newlines,
    phone2numeric,
    slugify,
    smart_split,
    unescape_string_literal,
    wrap,
)


def title_words(value):
    """Capitalise the first letter of every word and leave the rest as written."""
    return " ".join(word[:1].upper() + word[1:] for word in str(value).split(" "))


__all__ = [
    "title_words",
    "Truncator",
    "camel_case_to_spaces",
    "capfirst",
    "compress_sequence",
    "compress_string",
    "get_text_list",
    "get_valid_filename",
    "normalize_newlines",
    "phone2numeric",
    "slugify",
    "smart_split",
    "unescape_string_literal",
    "wrap",
]
