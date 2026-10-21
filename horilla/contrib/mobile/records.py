"""
Records tab (browse and search the opted-in models) and the record page.
"""

# First party imports (Horilla)
from horilla.core.exceptions import FieldDoesNotExist
from horilla.shortcuts import render
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _
from horilla.views.generic import TemplateView
from horilla.web import HttpResponse
from horilla.contrib.core.models import RecentlyViewed
from horilla.contrib.core.utils import get_field_permissions_for_model

# Local imports
from .access import can_list_model, can_log_activity, can_open, scope_queryset
from .activities import get_interactions, get_open_activities, get_type_colors
from .desktop import DesktopLayout
from .navigation import get_nav_items
from .registry import get_mobile_config, get_mobile_config_for_key, get_mobile_configs
from .search import MIN_QUERY_LENGTH, apply_search, tel_href
from .utils import user_display_name
from .views import MobilePageMixin

PAGE_SIZE = 20
# Rows per model in an "All" search before "Show all".
SEARCH_GROUP_SIZE = 5
RECENT_LIMIT = 5
# Values offered for a foreign-key filter.
FILTER_OPTION_LIMIT = 100
LAST_MODEL_SESSION_KEY = "mobile_records_model"
FILTER_PARAM_PREFIX = "f_"


def _hidden_fields(user, model):
    """Names of ``model`` fields hidden from ``user`` by field permissions."""
    return {
        name
        for name, permission in get_field_permissions_for_model(user, model).items()
        if permission == "hidden"
    }


def _label(model, name):
    """Verbose name of field ``name``."""
    return model._meta.get_field(name).verbose_name


def _default_ordering(model):
    """The model's own ordering, newest first when it declares none."""
    return model._meta.ordering or ["-pk"]


def record_url(obj):
    """Mobile record page URL of ``obj``."""
    meta = obj._meta
    return reverse("mobile:record", args=[meta.app_label, meta.model_name, obj.pk])


class RowPresenter:
    """
    What a list row shows for one model: title, status, a subtitle line, two
    labelled fields and a phone.
    """

    def __init__(self, config, user):
        self.config = config
        model = config.model
        hidden = _hidden_fields(user, model)
        self.title_field = (
            config.title_field if config.title_field not in hidden else ""
        )
        self.status_field = (
            config.status_field if config.status_field not in hidden else ""
        )
        self.subtitle_fields = [n for n in config.subtitle_fields if n not in hidden]
        self.row_fields = [
            (_label(model, name), name)
            for name in config.row_fields
            if name not in hidden
        ]
        self.phone_fields = [n for n in config.phone_fields if n not in hidden]
        names = [
            self.title_field,
            self.status_field,
            *self.subtitle_fields,
            *(name for _unused, name in self.row_fields),
        ]
        self.select_related = [
            name for name in names if name and model._meta.get_field(name).many_to_one
        ]

    def prepare(self, queryset):
        """Join the foreign keys the row renders."""
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        return queryset

    def rows(self, objects):
        """Row dicts for ``objects``."""
        return [self.row(obj) for obj in objects]

    def row(self, obj):
        """Row dict for one record."""
        phone = ""
        for name in self.phone_fields:
            phone = tel_href(getattr(obj, name, ""))
            if phone:
                break
        return {
            "obj": obj,
            "url": record_url(obj),
            "presenter": self,
            "phone_href": phone,
        }


class FilterSet:
    """
    Filters offered on the Records tab for one model: its status field and
    ``filter_fields`` from ``mobile.py``, each a set of values to pick from.
    """

    def __init__(self, config, user, params):
        self.config = config
        model = config.model
        hidden = _hidden_fields(user, model)
        names = []
        for name in (config.status_field, *config.filter_fields):
            if name and name not in hidden and name not in names:
                names.append(name)
        self.fields = []
        for name in names:
            options = self._options(model._meta.get_field(name))
            selected = set(params.getlist(f"{FILTER_PARAM_PREFIX}{name}"))
            valid = {value for value, _unused in options}
            self.fields.append(
                {
                    "name": name,
                    "param": f"{FILTER_PARAM_PREFIX}{name}",
                    "label": _label(model, name),
                    "options": [
                        {"value": value, "label": label, "selected": value in selected}
                        for value, label in options
                    ],
                    "selected": sorted(selected & valid),
                }
            )

    @staticmethod
    def _options(field):
        """``(value, label)`` pairs a field can be filtered by."""
        if getattr(field, "choices", None):
            return [(str(value), label) for value, label in field.flatchoices]
        if field.many_to_one:
            related = field.related_model
            queryset = related.objects.all()
            try:
                related._meta.get_field("order")
                queryset = queryset.order_by("order", "pk")
            except FieldDoesNotExist:
                queryset = queryset.order_by("pk")
            return [
                (str(obj.pk), user_display_name(obj))
                for obj in queryset[:FILTER_OPTION_LIMIT]
            ]
        return [("true", _("Yes")), ("false", _("No"))]

    @property
    def active(self):
        """The selected values, one chip each: field and value labels, param and value."""
        chips = []
        for field in self.fields:
            for option in field["options"]:
                if option["selected"]:
                    chips.append(
                        {
                            "field": field["label"],
                            "label": option["label"],
                            "param": field["param"],
                            "value": option["value"],
                        }
                    )
        return chips

    def apply(self, queryset):
        """Filter ``queryset`` by the selected values."""
        model = self.config.model
        for field in self.fields:
            values = field["selected"]
            if not values:
                continue
            model_field = model._meta.get_field(field["name"])
            if model_field.get_internal_type() == "BooleanField":
                booleans = {value == "true" for value in values}
                queryset = queryset.filter(**{f"{field['name']}__in": booleans})
            else:
                queryset = queryset.filter(**{f"{field['name']}__in": values})
        return queryset


class MobileRecordsView(MobilePageMixin, TemplateView):
    """
    Records tab. Without a search it lists one model's records (with filters
    and recently viewed); with a search it looks in every model at once.

    ``?partial=results`` returns the results area (search as you type, filter
    changes), ``?partial=rows`` the next page of rows, ``?partial=count`` the
    number of records the filter sheet would show.
    """

    template_name = "mobile/records.html"

    def get(self, request, *args, **kwargs):
        """Render the page, or the part ``?partial=`` asks for."""
        self.configs = [
            config
            for config in get_mobile_configs()
            if can_list_model(request.user, config.model)
        ]
        partial = request.GET.get("partial")
        if partial == "count":
            context = self.get_context_data(**kwargs)
            return HttpResponse(str(context.get("total", 0)))
        if partial == "rows":
            self.template_name = "mobile/partials/record_rows.html"
        elif partial == "results":
            self.template_name = "mobile/partials/records_results.html"
        return super().get(request, *args, **kwargs)

    def _selected_config(self):
        """Model being browsed: ``?model=``, else the last one, else the first."""
        request = self.request
        by_key = {config.key: config for config in self.configs}
        for key in (
            request.GET.get("model"),
            request.session.get(LAST_MODEL_SESSION_KEY),
        ):
            if key in by_key:
                return by_key[key]
        return self.configs[0] if self.configs else None

    def _page(self):
        """Requested page number (1-based)."""
        try:
            return max(1, int(self.request.GET.get("page", 1)))
        except (TypeError, ValueError):
            return 1

    def _paginate(self, queryset):
        """``(objects, next_page)`` for the requested page."""
        page = self._page()
        start = (page - 1) * PAGE_SIZE
        objects = list(queryset[start : start + PAGE_SIZE + 1])
        next_page = page + 1 if len(objects) > PAGE_SIZE else None
        return objects[:PAGE_SIZE], next_page

    def _url(self, drop=(), **changes):
        """
        This page's URL with the current query, ``changes`` applied (``None``
        removes a parameter) and ``(param, value)`` pairs in ``drop`` removed.
        """
        params = self.request.GET.copy()
        params.pop("partial", None)
        for key, value in changes.items():
            params.pop(key, None)
            if value is not None:
                params[key] = value
        for key, value in drop:
            params.setlist(key, [v for v in params.getlist(key) if v != value])
        query = params.urlencode()
        return (
            f"{reverse('mobile:records')}?{query}"
            if query
            else reverse("mobile:records")
        )

    def _base_queryset(self, config):
        """Records of ``config.model`` the user may view, in the model's order."""
        queryset = scope_queryset(self.request.user, config.model.objects.all())
        return queryset.order_by(*_default_ordering(config.model))

    def get_context_data(self, **kwargs):
        """Browse or search context."""
        context = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        context.update({"configs": self.configs, "query": query})
        if not self.configs:
            return context
        # Model the list returns to when the search is cleared.
        context["browse_key"] = self._selected_config().key
        if len(query) >= MIN_QUERY_LENGTH:
            context.update(self._search_context(query))
        else:
            context.update(self._browse_context())
        return context

    def _browse_context(self):
        """One model's records, filtered, with its recently viewed records."""
        request = self.request
        config = self._selected_config()
        request.session[LAST_MODEL_SESSION_KEY] = config.key
        presenter = RowPresenter(config, request.user)
        filters = FilterSet(config, request.user, request.GET)
        queryset = presenter.prepare(filters.apply(self._base_queryset(config)))
        objects, next_page = self._paginate(queryset)
        chips = filters.active
        for chip in chips:
            chip["remove_url"] = self._url(
                drop=[(chip["param"], chip["value"])], page=None
            )
        context = {
            "mode": "browse",
            "config": config,
            "filters": filters,
            "filter_chips": chips,
            "clear_filters_url": self._url(
                **{field["param"]: None for field in filters.fields}, page=None
            ),
            "rows": presenter.rows(objects),
            "next_url": (
                self._url(partial="rows", page=str(next_page)) if next_page else ""
            ),
            "total": queryset.count(),
            "show_type": False,
            "model_links": [
                {
                    "config": other,
                    "url": f"{reverse('mobile:records')}?model={other.key}",
                    "active": other == config,
                }
                for other in self.configs
            ],
        }
        if not filters.active and self._page() == 1:
            context["recent"] = presenter.rows(self._recently_viewed(config))
        return context

    def _recently_viewed(self, config):
        """The user's last opened records of ``config.model`` they can still open."""
        user = self.request.user
        recent = RecentlyViewed.objects.get_recently_viewed(
            user=user, model_class=config.model, limit=RECENT_LIMIT * 2
        )
        return [obj for obj in recent if can_open(user, obj)][:RECENT_LIMIT]

    def _search_context(self, query):
        """Matches in every model; ``?in=`` narrows to one model, paginated."""
        request = self.request
        narrowed = get_mobile_config_for_key(request.GET.get("in"))
        groups = []
        for config in self.configs:
            presenter = RowPresenter(config, request.user)
            queryset = presenter.prepare(
                apply_search(self._base_queryset(config), config, query)
            )
            count = queryset.count()
            if count:
                groups.append(
                    {
                        "config": config,
                        "count": count,
                        "presenter": presenter,
                        "queryset": queryset,
                    }
                )
        context = {"mode": "search", "groups": groups, "narrowed": None}
        context["total"] = sum(group["count"] for group in groups)
        context["all_url"] = self._url(**{"in": None, "page": None})
        for group in groups:
            group["url"] = self._url(**{"in": group["config"].key, "page": None})
        if narrowed and any(g["config"] == narrowed for g in groups):
            group = next(g for g in groups if g["config"] == narrowed)
            objects, next_page = self._paginate(group["queryset"])
            context.update(
                {
                    "narrowed": narrowed,
                    "rows": group["presenter"].rows(objects),
                    "next_url": (
                        self._url(partial="rows", page=str(next_page))
                        if next_page
                        else ""
                    ),
                    "show_type": False,
                }
            )
        else:
            for group in groups:
                group["rows"] = group["presenter"].rows(
                    group["queryset"][:SEARCH_GROUP_SIZE]
                )
                group["has_more"] = group["count"] > SEARCH_GROUP_SIZE
        return context


class MobileRecordView(MobilePageMixin, TemplateView):
    """Record page: header, Call and Email, key fields, activities and notes."""

    template_name = "mobile/record.html"

    def get(self, request, *args, **kwargs):
        """Open the record when it exists, is shown on the phone and the user may view it."""
        config = get_mobile_config(kwargs["app_label"], kwargs["model_name"])
        self.object = None
        if config is not None:
            self.object = config.model.objects.filter(pk=kwargs["pk"]).first()
        if self.object is None:
            return self._unavailable(
                _("This record doesn't exist or was deleted."), 404
            )
        if not can_open(request.user, self.object):
            return self._unavailable(
                _("You don't have permission to view this record."), 403
            )
        self.config = config
        RecentlyViewed.objects.add_viewed_item(request.user, self.object)
        return super().get(request, *args, **kwargs)

    @staticmethod
    def _owner_name(obj, owner_field):
        """Plain name of the record's owner, shown like the owner field below it."""
        owner = getattr(obj, owner_field, None) if owner_field else None
        return user_display_name(owner) if owner is not None else ""

    def _unavailable(self, message, status):
        """Phone-layout page saying why the record can't be shown."""
        return render(
            self.request,
            "mobile/unavailable.html",
            {
                "message": message,
                "mobile_nav_items": get_nav_items(self.request),
                "back_url": reverse("mobile:records"),
            },
            status=status,
        )

    def get_context_data(self, **kwargs):
        """Fields, actions, status choices and activity lists of the record."""

        context = super().get_context_data(**kwargs)
        user = self.request.user
        obj = self.object
        config = self.config
        hidden = _hidden_fields(user, config.model)
        layout = DesktopLayout(self.request, obj, config)

        phones = []
        for name in config.phone_fields:
            if name in hidden:
                continue
            value = getattr(obj, name, "") or ""
            href = tel_href(value)
            if href:
                phones.append(
                    {"label": _label(config.model, name), "value": value, "href": href}
                )
        email = ""
        if config.email_field and config.email_field not in hidden:
            email = getattr(obj, config.email_field, "") or ""

        open_rows, open_more = get_open_activities(user, obj)
        interaction_rows, interactions_more = get_interactions(user, obj)
        colors = get_type_colors(user)
        for row in (*open_rows, *interaction_rows):
            row.color = colors.get(row.kind, "")
        owner_fields = getattr(config.model, "OWNER_FIELDS", None) or []
        owner_field = next(
            (
                name
                for name in owner_fields
                if name not in hidden and config.model._meta.get_field(name).many_to_one
            ),
            "",
        )
        context.update(
            {
                "obj": obj,
                "config": config,
                "app_label": config.model._meta.app_label,
                "model_name": config.model._meta.model_name,
                "title_field": (
                    config.title_field if config.title_field not in hidden else ""
                ),
                "owner_name": self._owner_name(obj, owner_field),
                "subtitle_fields": [
                    name for name in config.subtitle_fields if name not in hidden
                ],
                "status": layout.get_status(),
                "status_field": (
                    config.status_field if config.status_field not in hidden else ""
                ),
                "key_fields": layout.get_key_fields(),
                "all_fields": layout.get_all_fields(),
                "phones": phones,
                "email": email,
                "open_activities": open_rows,
                "open_activities_more": open_more,
                "interactions": interaction_rows,
                "interactions_more": interactions_more,
                "can_log_activity": can_log_activity(user, obj),
                "desktop_url": layout.detail_path,
                "back_url": f"{reverse('mobile:records')}?model={config.key}",
            }
        )
        return context
