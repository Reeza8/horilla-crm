# Lead stages (`LeadStatus`)

Pipeline stages for leads. Configured under **Settings → Leads → Lead Status** and during **Initialize Database** step 5.

---

## Default stages constant

**`DEFAULT_LEAD_INIT_STAGES`** lives in `horilla_crm/leads/models/base.py` (exported from `horilla_crm.leads.models`).

Each entry is a dict: `name`, `order`, `probability`, `is_final`. Names use **`gettext_lazy`** for translation.

| Order | Name | Probability | Final |
|-------|------|-------------|-------|
| 1 | New | 10 | No |
| 2 | Contacted | 30 | No |
| 3 | Qualified | 60 | No |
| 4 | Proposal | 80 | No |
| 5 | Lost | 0 | No |
| 6 | Convert | 100 | Yes |

### Where the constant is used

| Consumer | Purpose |
|----------|---------|
| `LoadLeadStagesView` | Default template in init modal; signature comparison for “copy from other company” |
| `CustomStagesFormView` | Seed unique stage names when building custom form |
| `ensure_default_lead_stages_on_go_home` | Create stages when [Go To Home](../../horilla/contrib/core/initialize_database.md) skips the wizard |

Import:

```python
from horilla_crm.leads.models import DEFAULT_LEAD_INIT_STAGES, LeadStatus
```

Do not duplicate the stage list in views or signals — change **`DEFAULT_LEAD_INIT_STAGES`** only.

---

## Initialize Database flow

1. After company creation, **`company_created`** → HTMX loads `leads:load_lead_stages`.
2. User picks default stages, copies from another company, or defines custom stages.
3. **`CreateLeadStageGroupView`** saves rows and sends **`lead_stage_created`**.
4. When `initialization=True`, the opportunity init step is shown next.

### Go To Home shortcut

If the user clicks **Go To Home** on Role, Lead Stages, or Opportunity Stages (after user + company exist), **`initialize_database_go_home`** creates default lead stages when none exist. See [initialize_database.md](../../horilla/contrib/core/initialize_database.md).

---

## Settings UI

| View | Role |
|------|------|
| `LeadsStageView` | Shell — [settings list shell](../../horilla/contrib/core/settings_list_shell.md) |
| `LeadStageNavbar` | Navbar + filters |
| `LeadStageListView` | List of stages |
| `LeadStatusForm` / delete views | CRUD |

Settings shell: `template_name = "settings/settings_list_shell.html"`, `view_id = "leads-status-view"`.

---

## Signals

| Signal | Module | Role |
|--------|--------|------|
| `lead_stage_created` | `horilla_crm/leads/signals.py` | Post-save hook; drives opportunity init when `initialization=True` |
| `initialize_database_go_home` | `horilla.contrib.core.signals` | Listener: `ensure_default_lead_stages_on_go_home` |

---

## Kanban & detail pipeline

`is_final` is a **LeadStatus / OpportunityStage** concept. Generics do **not** interpret it.

| Layer | Behavior |
|-------|----------|
| `HorillaKanbanView` | FK columns expose **`related_obj`** (the stage instance). Bulk column counts; no `is_final` in the base class. |
| `LeadKanbanView` | When grouped by `lead_status`, skips columns where `getattr(related_obj, "is_final", False)`. |
| `LeadGroupByView` | When grouped by `lead_status`, drops final stage keys with one bulk `LeadStatus` query. |
| `HorillaDetailView` | Pipeline pills are dicts with **`related_obj`**; no `is_final` key from the base class. |
| `LeadDetailView` | Annotates `choice["is_final"]` from `related_obj.is_final` so `partials/pipeline_choices.html` + `final_stage_action` (convert modal) work. |

Docs: [kanban.md](../../horilla/contrib/generics/views/kanban.md), [details.md](../../horilla/contrib/generics/views/details.md).

---

## Related documentation

- [Assignment rules](assignment_rule.md)
- [Initialize Database](../../horilla/contrib/core/initialize_database.md)
- [Kanban generics](../../horilla/contrib/generics/views/kanban.md)
- [Detail generics](../../horilla/contrib/generics/views/details.md)
