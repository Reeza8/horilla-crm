"""
Utilities for generating and organizing file upload paths in Django models.

This module provides helpers to build unique, namespaced storage paths for
uploaded files (e.g. app_label/model_name/field_name/slug-uuid.ext) to avoid
collisions and keep uploads organized by app, model, and field.
"""

# Standard library imports
from uuid import uuid4

# First party imports (Horilla)
from horilla.utils.text import slugify


def upload_path(instance, filename):
    """
    Generates a unique file path for uploads in the format:
    app_label/model_name/field_name/originalfilename-uuid.ext
    """
    ext = filename.split(".")[-1]
    base_name = ".".join(filename.split(".")[:-1]) or "file"
    unique_name = f"{slugify(base_name)}-{uuid4().hex[:8]}.{ext}"

    # Try to find which field is uploading this file
    field_name = next(
        (
            k
            for k, v in instance.__dict__.items()
            if hasattr(v, "name") and v.name == filename
        ),
        None,
    )

    app_label = instance._meta.app_label
    model_name = instance._meta.model_name

    if field_name:
        return f"{app_label}/{model_name}/{field_name}/{unique_name}"
    return f"{app_label}/{model_name}/{unique_name}"
