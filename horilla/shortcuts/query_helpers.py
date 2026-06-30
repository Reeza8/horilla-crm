"""
Utility shortcuts for common Django operations.

This module provides convenient helper functions that extend Django's built-in
shortcuts functionality, particularly for handling object retrieval with proper
error handling.
"""

from django.http import Http404
from django.shortcuts import _get_queryset


def get_object_or_404(klass, *args, **kwargs):
    """
    Use get() to return an object, or raise an Http404 exception if the object
    does not exist.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Like with QuerySet.get(), MultipleObjectsReturned is raised if more than
    one object is found.
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "get"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_404() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist as exc:
        raise Http404(
            "%s matching query does not exist." % queryset.model._meta.verbose_name
        ) from exc
