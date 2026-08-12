"""Cadence detail view."""

# Standard library imports
from urllib.parse import urlparse

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin

from horilla.contrib.activity.models import Activity
from horilla.contrib.generics.views.details import HorillaDetailView
from horilla.db.models import Count

# First party imports (Horilla)
from horilla.urls import reverse
from horilla.utils.decorators import method_decorator, permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _

# Local imports
from ..models import Cadence


@method_decorator(
    permission_required_or_denied(["cadences.view_cadence"]),
    name="dispatch",
)
class CadenceDetailView(LoginRequiredMixin, HorillaDetailView):
    """Detail view for cadence (kanban-style conditions in columns)."""

    model = Cadence
    template_name = "cadence_detail.html"
    body = []
    actions = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = context.get("obj") or self.object
        referer_session_key = f"detail_referer_{self.model._meta.model_name}_{obj.pk}"
        stored_referer = self.request.session.get(referer_session_key)
        cadence_main_url = reverse("cadences:cadence_view")

        report_path = reverse("cadences:cadence_report_view")
        if stored_referer and urlparse(stored_referer).path == report_path:
            self.request.session.pop(referer_session_key, None)
            stored_referer = None

        context["previous_url"] = stored_referer or cadence_main_url
        followups = list(
            self.object.followups.select_related(
                "branch_from",
                "branch_from__branch_from",
                "email_template",
            )
            .annotate(branch_children_count=Count("branch_children"))
            .order_by("followup_number", "order", "id")
        )
        context["conditions"] = followups
        num_columns = self._display_column_count(followups)
        can_add_to_bucket, buckets = self._compute_can_add_to_bucket(
            followups, num_columns
        )
        cols_data = self._followups_into_columns(
            followups, num_columns, can_add_to_bucket, buckets
        )
        context["cadence_columns"] = [
            {
                "rows": cols_data[i],
                "col_num": i + 1,
                "show_bottom_sibling_add": (
                    i + 1 == 2 and len(buckets[2]) > 0 and can_add_to_bucket[2]
                ),
                "bottom_sibling_branch_from_id": (
                    buckets[1][0].pk if (i + 1 == 2 and len(buckets[1]) == 1) else None
                ),
            }
            for i in range(num_columns)
        ]
        context["followup_column_count"] = num_columns
        return context

    @staticmethod
    def _display_column_count(followups):
        if not followups:
            return 4
        return max(4, max(f.followup_number for f in followups) + 1)

    @staticmethod
    def _status_keys_for_previous_type(previous_type):
        if previous_type == "call":
            return {"scheduled", "completed", "overdue", "cancelled"}
        if previous_type == "task":
            return {key for key, _ in Activity.STATUS_CHOICES}
        return {
            "scheduled",
            "completed",
            "overdue",
            "cancelled",
            "in_progress",
            "not_started",
        }

    @classmethod
    def _compute_can_add_to_bucket(cls, followups, num_columns):
        buckets = {i: [] for i in range(1, num_columns + 1)}
        for followup in followups:
            bucket_no = max(1, min(num_columns, followup.followup_number))
            buckets[bucket_no].append(followup)

        can_add_to_bucket = {i: False for i in range(1, num_columns + 1)}
        can_add_to_bucket[1] = len(buckets[1]) == 0

        for bucket_no in range(2, num_columns + 1):
            prev_bucket_items = buckets[bucket_no - 1]
            if not prev_bucket_items:
                can_add_to_bucket[bucket_no] = False
                continue
            previous_type = prev_bucket_items[0].followup_type
            all_status_keys = cls._status_keys_for_previous_type(previous_type)
            used_statuses = {
                status
                for status in (
                    item.previous_status
                    for item in buckets[bucket_no]
                    if item.previous_status
                )
            }
            can_add_to_bucket[bucket_no] = bool(all_status_keys - used_statuses)
        return can_add_to_bucket, buckets

    @classmethod
    def _can_add_next_for_parent(cls, parent_followup, buckets, num_columns):
        next_bucket_no = parent_followup.followup_number + 1
        if next_bucket_no > num_columns:
            return False
        all_status_keys = cls._status_keys_for_previous_type(
            parent_followup.followup_type
        )
        used_statuses = {
            item.previous_status
            for item in buckets[next_bucket_no]
            if item.previous_status and item.branch_from_id == parent_followup.pk
        }
        return bool(all_status_keys - used_statuses)

    @classmethod
    def _can_add_same_stage_for_source(cls, source_followup, target_bucket_no, buckets):
        if not source_followup:
            return False
        all_status_keys = cls._status_keys_for_previous_type(
            source_followup.followup_type
        )
        used_statuses = {
            item.previous_status
            for item in buckets[target_bucket_no]
            if item.previous_status and item.branch_from_id == source_followup.pk
        }
        return bool(all_status_keys - used_statuses)

    @classmethod
    def _has_branch_child_in_next_bucket(cls, followup, buckets, num_columns):
        next_n = followup.followup_number + 1
        if next_n > num_columns:
            return False
        for item in buckets.get(next_n, []):
            if item.branch_from_id == followup.pk:
                return True
        return False

    @classmethod
    def _expand_fu1_column_slots(cls, rows):
        real = [r for r in rows if r.get("condition")]
        if not real:
            return rows
        real.sort(key=lambda r: (r["condition"].order, r["condition"].pk))
        return cls._expand_order_slots_for_branch_group(real)

    @classmethod
    def _rebuild_column_by_parent_slots(
        cls, row_dicts, followup_number, buckets, prev_column_rows=None
    ):
        real = [r for r in row_dicts if r.get("condition")]
        if not real:
            return row_dicts
        prev_fn = followup_number - 1
        parents = buckets.get(prev_fn, [])
        if not parents:
            real.sort(key=lambda r: (r["condition"].order, r["condition"].pk))
            return cls._expand_order_slots_for_branch_group(real)
        if prev_column_rows is not None:
            parents_ordered = []
            seen = set()
            for row in prev_column_rows:
                c = row.get("condition")
                if not c or c.pk in seen:
                    continue
                seen.add(c.pk)
                if c.followup_number == prev_fn:
                    parents_ordered.append(c)
            parent_ids = {p.pk for p in parents_ordered}
        else:
            parents_ordered = sorted(parents, key=lambda p: (p.order, p.pk))
            parent_ids = {p.pk for p in parents_ordered}
        by_parent = {pid: [] for pid in parent_ids}
        orphans = []
        for r in real:
            bf = r["condition"].branch_from_id
            if bf and bf in parent_ids:
                by_parent[bf].append(r)
            else:
                orphans.append(r)
        for pid in by_parent:
            by_parent[pid].sort(key=lambda r: (r["condition"].order, r["condition"].pk))
        out = []
        for p in parents_ordered:
            group = by_parent.get(p.pk, [])
            if group:
                out.extend(cls._expand_order_slots_for_branch_group(group))
            # Parents with no continuation in this stage contribute no row at all;
            # the flow-arrow script matches cards by pk/position rather than row
            # index, so skipping them just makes the column shorter instead of
            # reserving a blank card.
        if orphans:
            orphans.sort(key=lambda r: (r["condition"].order, r["condition"].pk))
            out.extend(cls._expand_order_slots_for_branch_group(orphans))
        return out

    @classmethod
    def _expand_order_slots_for_branch_group(cls, group_rows):
        max_order = max(r["condition"].order for r in group_rows)
        by_order = {}
        for r in group_rows:
            by_order.setdefault(r["condition"].order, []).append(r)
        out = []
        for s in range(0, max_order + 1):
            if s in by_order:
                out.extend(by_order[s])
            else:
                out.append({"empty_slot": True, "slot_order": s})
        return out

    @staticmethod
    def _stage2_source_pk(followup):
        source = followup.branch_from
        while source and source.followup_number > 2 and source.branch_from_id:
            source = source.branch_from
        if source and source.followup_number == 2:
            return source.pk
        return None

    @classmethod
    def _followups_into_columns(
        cls, followups, num_columns, can_add_to_bucket, buckets
    ):
        _CONDITION_CARD_ICONS = (
            "assets/icons/task.svg",
            "assets/icons/call.svg",
            "assets/icons/email_outline.svg",
        )
        _CONDITION_LABELS = (_("Task"), _("Call"), _("Email"))
        _KIND = ("task", "call", "email")
        icon_by_kind = dict(zip(_KIND, _CONDITION_CARD_ICONS))
        label_by_kind = dict(zip(_KIND, _CONDITION_LABELS))
        cols = [[] for _ in range(num_columns)]
        for followup in followups:
            idx = max(1, min(num_columns, followup.followup_number)) - 1
            kind = followup.followup_type
            fu_n = followup.followup_number
            if fu_n == 1:
                can_add_next_bucket = fu_n < num_columns and can_add_to_bucket.get(
                    fu_n + 1, False
                )
            else:
                can_add_next_bucket = cls._can_add_next_for_parent(
                    followup, buckets, num_columns
                )

            has_next_child = cls._has_branch_child_in_next_bucket(
                followup, buckets, num_columns
            )
            if fu_n == 1:
                show_card_add_branch = len(buckets[2]) == 0 and can_add_to_bucket.get(
                    2, False
                )
            elif fu_n < num_columns:
                show_card_add_branch = can_add_next_bucket and not has_next_child
            else:
                show_card_add_branch = False
            add_branch_followup_number = (
                fu_n + 1 if fu_n < num_columns and show_card_add_branch else None
            )
            bottom_add_followup_number = None
            bottom_add_branch_from_id = None
            if fu_n >= 3:
                source_same_stage = (
                    followup.branch_from
                    if followup.branch_from_id
                    and followup.branch_from.followup_number == fu_n - 1
                    else None
                )
                if source_same_stage and cls._can_add_same_stage_for_source(
                    source_same_stage, fu_n, buckets
                ):
                    bottom_add_followup_number = fu_n
                    bottom_add_branch_from_id = source_same_stage.pk
            cols[idx].append(
                {
                    "condition": followup,
                    "icon": icon_by_kind.get(kind, _CONDITION_CARD_ICONS[0]),
                    "kind_label": label_by_kind.get(kind, _CONDITION_LABELS[0]),
                    "kind": kind,
                    "can_add_next": can_add_next_bucket,
                    "show_card_add_branch": show_card_add_branch,
                    "show_card_add_below_next": bool(bottom_add_followup_number),
                    "bottom_add_followup_number": bottom_add_followup_number,
                    "bottom_add_branch_from_id": bottom_add_branch_from_id,
                    "add_branch_followup_number": add_branch_followup_number,
                    "show_child_down_arrow": False,
                    "show_delete_followup": getattr(
                        followup, "branch_children_count", 0
                    )
                    == 0,
                }
            )
        for i in range(num_columns):
            fn = i + 1
            if fn == 1:
                cols[i] = cls._expand_fu1_column_slots(cols[i])
            else:
                cols[i] = cls._rebuild_column_by_parent_slots(
                    cols[i], fn, buckets, prev_column_rows=cols[i - 1]
                )
        for col_idx in range(2, num_columns):
            cls._apply_fu3_column_visual_flags(cols[col_idx])
        return cols

    @classmethod
    def _apply_fu3_column_visual_flags(cls, cols_2):
        real_indices = [i for i, r in enumerate(cols_2) if r.get("condition")]
        for idx, i in enumerate(real_indices):
            row = cols_2[i]
            source_pk = cls._stage2_source_pk(row["condition"])
            if idx + 1 < len(real_indices):
                j = real_indices[idx + 1]
                next_source_pk = cls._stage2_source_pk(cols_2[j]["condition"])
                row["show_child_down_arrow"] = bool(
                    source_pk and source_pk == next_source_pk
                )
            else:
                row["show_child_down_arrow"] = False
        next_source_pk = None
        for i in range(len(cols_2) - 1, -1, -1):
            row = cols_2[i]
            if not row.get("condition"):
                continue
            source_pk = cls._stage2_source_pk(row["condition"])
            has_child_in_path = bool(source_pk and source_pk == next_source_pk)
            row["has_child_in_path"] = has_child_in_path
            if has_child_in_path:
                row["show_card_add_below_next"] = False
            next_source_pk = source_pk
