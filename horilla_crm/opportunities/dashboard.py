"""Dashboard utilities for opportunities module."""

# Standard library imports
import logging

# Third-party imports (Django)
from django.utils.http import urlencode

from horilla.contrib.dashboard.utils import DefaultDashboardGenerator
from horilla.contrib.utils.methods import get_section_info_for_model

# First party imports (Horilla)
from horilla.db.models import Count
from horilla.utils.choices import TABLE_FALLBACK_FIELD_TYPES
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import Opportunity

logger = logging.getLogger(__name__)


def create_opportunity_charts(self, queryset, model_info):
    """Create opportunity-specific charts"""
    try:
        if hasattr(queryset.model, "lead_source") or hasattr(queryset.model, "source"):
            source_field = (
                "lead_source" if hasattr(queryset.model, "lead_source") else "source"
            )
            source_data = (
                queryset.values(source_field)
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            if source_data.exists():
                labels = [item[source_field] or "Unknown" for item in source_data]
                data = [item["count"] for item in source_data]

                section_info = get_section_info_for_model(queryset.model)
                urls = []
                for item in source_data:
                    value = item[source_field] or "Unknown"
                    query = urlencode(
                        {
                            "section": section_info["section"],
                            "apply_filter": "true",
                            "field": source_field,
                            "operator": "exact",
                            "value": value,
                        }
                    )
                    urls.append(f"{section_info['url']}?{query}")

                return {
                    "title": _("Opportunities by Lead Source"),
                    "type": "column",
                    "data": {
                        "labels": labels,
                        "urls": urls,
                        "data": data,
                        "labelField": "Lead Source",
                    },
                }

        stage_field = None
        if hasattr(queryset.model, "stage"):
            stage_field = "stage"
        elif hasattr(queryset.model, "status"):
            stage_field = "status"
        elif hasattr(queryset.model, "opportunity_stage"):
            stage_field = "opportunity_stage"

        if stage_field:
            stage_data = (
                queryset.values(stage_field)
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            if stage_data.exists():
                labels = [item[stage_field] or "Unknown" for item in stage_data]
                data = [item["count"] for item in stage_data]

                return {
                    "title": _("Opportunities by Stage"),
                    "type": "funnel",
                    "data": {"labels": labels, "data": data, "labelField": "Stage"},
                }

        if hasattr(queryset.model, "is_won"):
            won_data = queryset.values("is_won").annotate(count=Count("id"))

            if won_data.exists():
                labels = []
                data = []
                for item in won_data:
                    status = "Won" if item["is_won"] else "In Progress/Lost"
                    labels.append(status)
                    data.append(item["count"])

                return {
                    "title": _("Opportunity Win Rate"),
                    "type": "pie",
                    "data": {
                        "labels": labels,
                        "data": data,
                        "labelField": "Status",
                    },
                }

        if hasattr(queryset.model, "amount") or hasattr(queryset.model, "value"):
            amount_field = "amount" if hasattr(queryset.model, "amount") else "value"

            opportunities = list(
                queryset.values("id", amount_field).exclude(
                    **{f"{amount_field}__isnull": True}
                )
            )
            if opportunities:
                ranges = ["<10K", "10K-50K", "50K-100K", "100K+"]
                range_counts = [0, 0, 0, 0]

                for opp in opportunities:
                    amount = float(opp[amount_field] or 0)
                    if amount < 10000:
                        range_counts[0] += 1
                    elif amount < 50000:
                        range_counts[1] += 1
                    elif amount < 100000:
                        range_counts[2] += 1
                    else:
                        range_counts[3] += 1

                return {
                    "title": _("Opportunities by Value Range"),
                    "type": "column",
                    "data": {
                        "labels": ranges,
                        "data": range_counts,
                        "labelField": "Value Range",
                    },
                }

    except Exception as e:
        logger.warning("Error creating opportunity chart: %s", e)

    return None


def opportuntiy_table_fields(model_class):
    """Return list of {name, verbose_name} for opportuntiy table columns."""

    priority = ["name", "title", "account", "amount", "stage"]
    fields = []
    for name in priority:
        try:
            f = model_class._meta.get_field(name)
            fields.append(
                {
                    "name": name,
                    "verbose_name": f.verbose_name or name.replace("_", " ").title(),
                }
            )
        except Exception:
            continue
    if len(fields) < 4:
        for f in model_class._meta.fields:
            if len(fields) >= 4:
                break
            if (
                f.name not in [x["name"] for x in fields]
                and f.get_internal_type() in TABLE_FALLBACK_FIELD_TYPES
            ):
                fields.append(
                    {
                        "name": f.name,
                        "verbose_name": f.verbose_name
                        or f.name.replace("_", " ").title(),
                    }
                )
    return fields


def opportunity_table_func(generator, model_info):
    """Generate table context for won opportunities."""
    filter_kwargs = (
        {"stage__name": "Closed Won"} if hasattr(model_info["model"], "stage") else {}
    )

    return generator.build_table_context(
        model_info=model_info,
        title=_("Closed Won Opportunities"),
        filter_kwargs=filter_kwargs,
        no_found_img="assets/img/not-found-list.svg",
        no_record_msg="No closed won opportunities found.",
        view_id="opportunities_dashboard_list",
    )


DefaultDashboardGenerator.extra_models.append(
    {
        "model": Opportunity,
        "name": _("Opportunities"),
        "icon": "fa-handshake",
        "color": "purple",
        "include_kpi": True,
        "chart_func": create_opportunity_charts,
        "table_func": opportunity_table_func,
        "table_fields_func": opportuntiy_table_fields,
    }
)
