# Initialize Database workflow (`horilla.contrib.core.views.initialiaze_database`)

First-run onboarding runs only while no users exist in the database. Views are gated with **`@db_initialization`** and a session password (`settings.DB_INIT_PASSWORD`). See [decorators — `db_initialization`](../../utils/decorators.md#-db_initialization).

---

## Progress steps

`ProgressStepsMixin` + `BASE_STEPS` drive the step indicator in init templates.

| Step | View | Purpose |
|------|------|---------|
| 1 | `InitializeDatabase` | DB init password |
| 2 | `InitializeDatabaseUser` | Superuser sign-up |
| 3 | `InitializeDatabaseCompany` | First company |
| 4 | `InitializeRoleView` | Role hierarchy |
| 5 | Lead stages init (CRM) | `leads:load_lead_stages` / `CreateLeadStageGroupView` |
| 6 | Opportunity stages init (CRM) | `opportunities:load_opportunity_stages` / `CreateOppStageGroupView` |

After company creation, **`company_created`** listeners inject HTMX scripts that load the lead-stage modal for new companies.

---

## Go To Home (skip remaining steps)

Users who finish **user sign-up** and **company setup** can exit the wizard without completing Role, Lead Stages, or Opportunity Stages.

| Piece | Location |
|-------|----------|
| View | `InitializeDatabaseGoHomeView` |
| URL | `core:initialize_database_go_home` → `initialize-database-go-home/` |
| Button partial | `initialize_database/go_to_home_button.html` |
| Included on | `initialize_role.html`, `lead_stages_initialize.html`, `oppor_stages_initialize.html` |

### Button UX

The link is styled as a text action (`text-sm text-primary-600 hover:underline`), not a filled button. **Next Step** on the Role step remains the primary filled control.

### Guards

`InitializeDatabaseGoHomeView.get()` requires:

1. At least one `User` and one `Company` in the database.
2. Otherwise → error message and redirect to the user or company init step.

On success:

1. Resolves the active `Company` from `request.user.company_id`, session `company_id`, or `request.user.company`.
2. Sends **`initialize_database_go_home`** (see below).
3. Clears session keys `db_password` and `company_id`.
4. Redirects to **`settings.DEFAULT_HOME_REDIRECT`** (typically `/dashboard/?section=home`).

---

## Signal: `initialize_database_go_home`

Defined in **`horilla.contrib.core.signals`**. Fired when the init wizard exits early via Go To Home.

```python
initialize_database_go_home.send(
    sender=InitializeDatabaseGoHomeView,
    company=company,
    request=request,
)
```

| Kwarg | Type | Role |
|-------|------|------|
| `company` | `Company` | Company to seed stages for |
| `request` | `HttpRequest` | Used for `created_by` on new rows |

### Listeners (CRM)

| Receiver | Module | Behavior |
|----------|--------|----------|
| `ensure_default_lead_stages_on_go_home` | `horilla_crm.leads.signals` | Creates rows from **`DEFAULT_LEAD_INIT_STAGES`** when no `LeadStatus` exists for the company |
| `ensure_default_opportunity_stages_on_go_home` | `horilla_crm.opportunities.signals` | Creates rows from **`DEFAULT_OPPORTUNITY_INIT_STAGES`** when no `OpportunityStage` exists; sets `stage_type` (`open` / `won` / `lost`) from probability |

Both receivers **no-op** if stages already exist, so completing the full wizard is unchanged.

Stage constants and full wizard flow:

- [Lead stages](../../../horilla_crm/leads/lead_stages.md)
- [Opportunity stages](../../../horilla_crm/opportunities/opportunity_stages.md)

---

## Related signals

| Signal | When |
|--------|------|
| `company_created` | New company saved — triggers lead-stage load script |
| `lead_stage_created` | Lead stage group saved — opportunity init step when `initialization=True` |
| `opp_stage_created` | Opportunity stage group saved |

---

## Source files

| File | Role |
|------|------|
| `horilla/contrib/core/views/initialiaze_database.py` | All init + Go Home views |
| `horilla/contrib/core/signals.py` | `initialize_database_go_home` |
| `horilla/contrib/core/urls.py` | URL routes |
| `horilla/contrib/core/progress.py` | Step definitions |
| `horilla/contrib/core/templates/initialize_database/` | Init templates + Go Home button |

---

## Related documentation

- [Core app index](core_app.md)
- [`db_initialization` decorator](../../utils/decorators.md#-db_initialization)
- [Settings list shell](settings_list_shell.md) (settings pages after onboarding)
