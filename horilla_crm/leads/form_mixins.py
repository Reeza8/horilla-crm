"""
Form mixin that adds "Apply assignment rule" to the lead create forms.

When at least one active assignment rule exists, a new lead's form shows an
"Apply assignment rule" switch. With it on:

* the Owner field is limited to the people the matching rule can assign to,
  with the person who currently owns the fewest leads pre-selected;
* the lead must satisfy a rule condition, otherwise the form is rejected;
* the form records its decision on the lead (``_assignment_condition_id``) so
  the post-save engine does not pick an owner a second time.

With it off nothing changes: the owner is the one picked in the form.

The mixin has to be the outermost base of the form, in front of
``OwnerQuerysetMixin``, because that mixin sets the owner queryset at the end
of its own ``__init__``.
"""

# Standard library imports
import json

# Third-party imports (Django)
from django import forms

# First party imports (Horilla)
from horilla.contrib.generics.forms.condition_fields import (
    get_condition_field_extension,
)
from horilla.urls import reverse_lazy
from horilla.utils.html import format_html
from horilla.utils.translation import gettext_lazy as _

# Local imports
from horilla_crm.leads.assignment.pool import (
    MATCHED,
    NO_ASSIGNEES,
    NO_MATCH,
    OWNER_FIELD,
    UNDETERMINED,
    VIA_FORM,
    active_conditions,
    build_assignment_info,
    has_active_rules,
    resolve_for_data,
    union_resolution,
)

APPLY_FIELD = "apply_assignment_rule"

# Class of the select shown for the owner while the rule is applied. It is a
# plain select with the people already listed: the ajax select the owner field
# normally uses would load every user again and ignore the restriction.
OWNER_SELECT_CLASS = "js-example-basic-single headselect"

# The switch lives in a field container whose owner select has this id; the
# browser swaps the content of the box around the select.
OWNER_BOX_SELECTOR = f"div:has(> #id_{OWNER_FIELD})"


class LeadAssignmentRuleFormMixin:
    """Adds the "Apply assignment rule" option to a lead create form."""

    # Set by the preview endpoint: the form only answers "who can be the owner",
    # so it must not treat missing values as final.
    _assignment_preview = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment_resolution = None
        self._assignment_decision = None
        self._pool_mode = False

        if not self._assignment_applicable():
            return

        checked = self._apply_requested()
        self._add_apply_field(checked)
        if checked:
            self._enter_pool_mode(union_resolution(self._assignment_company()))

    # ------------------------------------------------------------------ setup

    def _assignment_applicable(self):
        """The option is offered on create forms while an active rule exists."""
        if self.instance is not None and self.instance.pk:
            return False
        return has_active_rules()

    def _assignment_company(self):
        """Company whose people can be assigned: the request's active company."""
        request = getattr(self, "request", None)
        if request is None:
            return None
        return getattr(request, "active_company", None) or getattr(
            request.user, "company", None
        )

    def _is_multi_step(self):
        return bool(getattr(self, "step_fields", None))

    def _apply_requested(self):
        """Whether the switch is on in the submitted (or stored) data."""
        data = getattr(self, "data", None)
        if not data:
            return False
        return forms.CheckboxInput().value_from_datadict(
            data, getattr(self, "files", None), self.add_prefix(APPLY_FIELD)
        )

    def _criteria_fields(self):
        """Names of the fields the active rules look at, in a stable order."""
        names = []
        for condition in active_conditions():
            for criteria in condition.criteria.all():
                if criteria.field not in names:
                    names.append(criteria.field)
        return names

    def _htmx_attrs(self):
        """Attributes that make the switch reload the owner field."""
        fields = self._criteria_fields()
        include = ", ".join(f"[name='{name}']" for name in [OWNER_FIELD, *fields])
        # Reload when the switch itself is toggled and, while it is on, when a
        # field the rules depend on changes. The field is listened to directly:
        # select2 sends its change to the select only, it does not bubble to the
        # form. A change of the owner itself must not reload it, or the dropdown
        # would reset while it is being used.
        mode = "multi" if self._is_multi_step() else "single"
        triggers = ["change"]
        triggers += [f"change[this.checked] from:#id_{name}" for name in fields]
        trigger = ", ".join(triggers)
        return {
            "hx-get": reverse_lazy("leads:assignment_rule_owner"),
            "hx-trigger": trigger,
            "hx-include": include,
            "hx-target": OWNER_BOX_SELECTOR,
            "hx-swap": "innerHTML",
            "hx-sync": "this:replace",
            "hx-vals": json.dumps({"mode": mode}),
            "class": "sr-only peer",
        }

    def _add_apply_field(self, checked):
        """Add the switch right after the owner field."""
        field = forms.BooleanField(
            required=False,
            initial=checked,
            label=_("Apply assignment rule"),
            help_text=_(
                "Pick the owner from the people the matching assignment rule "
                "can assign to."
            ),
            widget=forms.CheckboxInput(attrs=self._htmx_attrs()),
        )
        ordered = {}
        for name, existing in self.fields.items():
            ordered[name] = existing
            if name == OWNER_FIELD:
                ordered[APPLY_FIELD] = field
        ordered.setdefault(APPLY_FIELD, field)
        self.fields = ordered

    def get_fields_for_step(self, step):
        """
        On the wizard, show the switch right after Owner on the first step.

        The switch is not listed in ``step_fields``: the wizard's own ``clean``
        looks every listed name up on the model and fails for a name that is
        not a model field.
        """
        parent = getattr(super(), "get_fields_for_step", None)
        fields = parent(step) if parent else self.visible_fields()
        if step != 1 or APPLY_FIELD not in self.fields or not self._is_multi_step():
            return fields
        shown = []
        for bound in fields:
            shown.append(bound)
            if bound.name == OWNER_FIELD:
                shown.append(self[APPLY_FIELD])
        if len(shown) == len(fields):
            shown.insert(0, self[APPLY_FIELD])
        return shown

    # -------------------------------------------------------------- owner pool

    def _enter_pool_mode(self, resolution):
        """Limit the owner field to ``resolution.users`` as a flat list of people."""
        owner = self.fields.get(OWNER_FIELD)
        if owner is None:
            return
        self._pool_mode = True
        # The generic form re-checks that the user may assign to the chosen
        # owner; people of a rule can be assigned whatever the user's own
        # permissions are, and membership of the pool is checked in clean().
        self._unrestricted_fields = set(getattr(self, "_unrestricted_fields", ())) | {
            OWNER_FIELD
        }
        owner.queryset = resolution.users
        if owner.widget.is_hidden:
            # A later step of the multi-step form keeps the owner as a hidden input.
            return

        choices = [("", "---------")]
        seen = set()
        for _label, users in resolution.groups:
            for user in users:
                if user.pk not in seen:
                    seen.add(user.pk)
                    choices.append((user.pk, str(user).strip() or user.username))
        owner.widget = forms.Select(
            choices=choices,
            attrs={"class": OWNER_SELECT_CLASS, "id": f"id_{OWNER_FIELD}"},
        )
        current = self.data.get(OWNER_FIELD) if self.data else None
        if current:
            self.initial[OWNER_FIELD] = current

    def _prefer_owner(self, resolution):
        """Select the least-loaded person unless the chosen owner is in the pool."""
        owner = resolution.default_owner
        if owner is None:
            return
        current = self.data.get(OWNER_FIELD) if self.data else None
        if str(current).isdigit() and resolution.users.filter(pk=current).exists():
            return
        data = self.data.copy()
        data[OWNER_FIELD] = owner.pk
        self.data = data

    # --------------------------------------------------------------- validation

    def _assignment_is_final(self):
        """True when the form holds every value a rule can look at."""
        if self._assignment_preview:
            return False
        if self._is_multi_step():
            return getattr(self, "current_step", 1) >= max(self.step_fields)
        return True

    def _unknown_names(self):
        """Fields whose value is not available yet on this step of the wizard."""
        if not self._is_multi_step() or self._assignment_is_final():
            return set()
        current = getattr(self, "current_step", 1)
        later = {
            name
            for step, names in self.step_fields.items()
            if step > current
            for name in names
        }
        # Custom fields are asked on the last step.
        custom = {name for name in self.fields if self._is_extension_field(name)}
        return later | custom

    @staticmethod
    def _is_extension_field(name):
        """True for a field that is not a Lead column, e.g. a custom field."""
        return get_condition_field_extension(name) is not None

    def _rule_data(self, cleaned_data):
        """The values the rules are checked against."""
        unknown = self._unknown_names()
        data = {
            name: value for name, value in cleaned_data.items() if name not in unknown
        }
        if self._assignment_preview:
            # The user may not have got to a blank field yet.
            data = {
                name: value
                for name, value in data.items()
                if value not in (None, "", [], ())
            }
        # Lead fields that are not on the form keep the value a new lead has.
        for name in self._criteria_fields():
            if name in data or name in self.fields or name in unknown:
                continue
            if self._is_extension_field(name):
                continue
            if hasattr(self.instance, name):
                data[name] = getattr(self.instance, name)
        return data

    def _owner_error(self, message):
        """Attach an owner error to the field when it is shown, else to the form."""
        owner = self.fields.get(OWNER_FIELD)
        if owner is not None and not owner.widget.is_hidden:
            self.add_error(OWNER_FIELD, message)
        else:
            self.add_error(None, message)

    def clean(self):
        """Check the lead against the rules when the switch is on."""
        cleaned_data = super().clean()
        if cleaned_data is None or not cleaned_data.get(APPLY_FIELD):
            return cleaned_data
        self._validate_assignment(cleaned_data)
        return cleaned_data

    def _validate_assignment(self, cleaned_data):
        final = self._assignment_is_final()
        if final and self._errors:
            # A value that failed its own validation is not known; the form is
            # rejected anyway and a "no match" would only add noise.
            final = False

        resolution = resolve_for_data(
            self._rule_data(cleaned_data),
            final=final,
            company=self._assignment_company(),
        )
        self.assignment_resolution = resolution

        if resolution.state == NO_ASSIGNEES:
            self.add_error(None, resolution.reason)
            return
        if resolution.state == NO_MATCH:
            self.add_error(None, self._no_match_message(resolution.reason))
            return

        self._enter_pool_mode(resolution)
        if resolution.state != MATCHED:
            # Which rule applies is not settled yet, so nobody is suggested.
            return
        if self._assignment_preview and self.fields.get(OWNER_FIELD) is not None:
            self._prefer_owner(resolution)

        owner = cleaned_data.get(OWNER_FIELD)
        if owner is None:
            return
        if not resolution.users.filter(pk=owner.pk).exists():
            self._owner_error(
                _("Choose one of the people rule “%(rule)s” assigns to.")
                % {"rule": resolution.rule.name}
            )
            return
        if final:
            self._assignment_decision = (resolution.condition, owner)

    @staticmethod
    def _no_match_message(reason):
        message = _(
            "The lead does not satisfy any active assignment rule%(reason)s. "
            "Change the values or untick “Apply assignment rule”."
        )
        return message % {"reason": f" ({reason})" if reason else ""}

    # ------------------------------------------------------------------- saving

    def save(self, commit=True):
        """Tell the post-save engine the owner was already decided by a rule."""
        decision = self._assignment_decision
        if decision is not None:
            condition, owner = decision
            self.instance._assignment_condition_id = condition.pk
            self.instance.additional_info = build_assignment_info(
                self.instance.additional_info, condition, owner, VIA_FORM
            )
        return super().save(commit=commit)

    # ------------------------------------------------------------------ preview

    def render_owner_preview(self):
        """
        HTML that replaces the Owner field while the switch is toggled.

        Switch off: the owner field as the form normally renders it. Switch on:
        the owner field limited to the rule's people, with a short note.
        """
        resolution = self.assignment_resolution
        if not self._apply_requested() or resolution is None:
            return str(self[OWNER_FIELD])

        if resolution.state == MATCHED:
            note = _("Assigned by rule “%(rule)s”.") % {"rule": resolution.rule.name}
            css = "text-gray-500"
        elif resolution.state == UNDETERMINED:
            note = _("The rule is confirmed when the remaining fields are filled in.")
            css = "text-gray-500"
        elif resolution.state == NO_ASSIGNEES:
            note = resolution.reason
            css = "text-red-500"
        else:
            note = self._no_match_message(resolution.reason)
            css = "text-red-500"

        if resolution.state in (NO_MATCH, NO_ASSIGNEES):
            # Nobody can be picked from a rule, so show the owner field as it
            # is without the switch.
            data = self.data.copy()
            data.pop(APPLY_FIELD, None)
            plain = self.__class__(data=data, request=self.request)
            field_html = str(plain[OWNER_FIELD])
        else:
            field_html = str(self[OWNER_FIELD])
        return format_html('{}<p class="text-xs mt-1 {}">{}</p>', field_html, css, note)
