"""
Horilla authentication mixins.

Provides mixins for Django views to handle authentication and authorization.
"""

from django.contrib.auth.mixins import LoginRequiredMixin

__all__ = [
    "LoginRequiredMixin",
]
