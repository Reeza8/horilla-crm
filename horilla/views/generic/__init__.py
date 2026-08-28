"""Horilla generic views package. Re-exports FormView for callers."""

from horilla.views.generic.edit import FormView
from horilla.views.generic.base import View, TemplateView
from horilla.views.generic.list import ListView
from horilla.views.generic.detail import DetailView

__all__ = ["FormView", "View", "TemplateView", "ListView", "DetailView"]
