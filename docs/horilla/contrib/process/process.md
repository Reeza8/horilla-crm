# Horilla Process apps — deep dive (`horilla.contrib.process.*`)

Parent package **`horilla.contrib.process`** bundles two independent Django apps that share no single `AppLauncher`—each has its own `apps.py`, migrations, and URL namespace.

---

## Approvals (`horilla.contrib.process.approvals`)

### Purpose

Generic **multi-step approval** engine: rules bind to any model registered under the **`approval_models`** feature, with steps, approvers, conditions, running **instances**, and immutable **decisions**.

### `ApprovalsConfig`

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.process.approvals` |
| `label` | `approvals` |
| `url_prefix` | `approvals/` |
| `url_namespace` | `approvals` |
| `auto_import_modules` | `registration`, `signals`, `menu` |

### Feature registration (`registration.py`)

```text
register_feature("approvals", "approval_models", auto_register_all=False)
```

`auto_register_all=False` means **opt-in only**—each business app must register eligible models; nothing is auto-approved globally.

### Model stack (summary)

| Model | Role |
|-------|------|
| `ApprovalRule` | Template: which `ContentType`, trigger events, active flag. |
| `ApprovalProcessRule` | Links rules into ordered processes. |
| `ApprovalStep` | Approver role/user, ordering, SLA hints. |
| `ApprovalCondition` | Field-level gating before a step fires. |
| `ApprovalInstance` | Live state machine row for one target object. |
| `ApprovalDecision` | Who approved/rejected, timestamps, comments. |

### UX integration

- Detail views may embed approval status via generics tabs or partials (`templates/` under approvals).
- Menu entries open approval job queues for managers.
- Job detail uses **`approval_job_detail_page.html`** (body partial + tab container height) when opening an approval job from the queue.
- List views that hide rows with a pending approval instance cast object ids consistently when excluding pending PKs (avoids type-mismatch misses between `str`/`int` id sets).
- **`ApprovalListVisibilityExtension`** (`MixinExtension` on list views) replaces earlier monkey patches for pending-approval row visibility; **`ApprovalGuardBulkEditExtension`** (`_inherit_view` on `UpdateAllFieldsView`) blocks bulk Edit Details when an approval guard raises.

---

## Review Process (`horilla.contrib.process.reviews`)

### Purpose

Structured **review cycles** (360 / performance-style) with configurable rules, participants, and **jobs** tracking progress.

### `ReviewProcessConfig`

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.process.reviews` |
| `label` | `reviews` |
| `url_prefix` | `review-process/` |
| `url_namespace` | `reviews` |
| `auto_import_modules` | `registration`, `signals`, `menu` |

### Model stack (summary)

| Model | Role |
|-------|------|
| `ReviewProcess` | Definition: frequency, anonymity, rating scales. |
| `ReviewCondition` / `ReviewRule` / `ReviewRuleCondition` | Eligibility and scoring matrix. |
| `ReviewJob` | Concrete assignment batch per employee/period. |

### Global `post_save` handler (`signals.py`)

`reviews_post_save_handler` is connected once at import time. It checks `FEATURE_REGISTRY` at **dispatch** time (not at `ready()`), because target apps register review-enabled models after the reviews app starts. Per-model connections at startup would miss late-registered models.

### List visibility

**`ReviewListVisibilityExtension`** (`MixinExtension`) replaces earlier monkey patches that hid or filtered review-related list rows.

---

## Cross-cutting concerns

- Both apps rely on **`HorillaContentType`** for polymorphic links—see [../core/models.md](../core/models.md).
- Permissions follow standard `AppLauncher` + `register_model_for_feature` patterns in each app’s `registration.py` (read files for exact model lists).

---

## Related documentation

- Generics detail tabs embedding process widgets: [../generics/views/detail_tabs.md](../generics/views/detail_tabs.md)
- Permission registry concepts: [../core/Registry/permission_registry.md](../core/Registry/permission_registry.md)
