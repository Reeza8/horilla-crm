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

__all__ = [
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
