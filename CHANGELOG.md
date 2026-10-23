# Changelog

All notable changes to Horilla CRM are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file starts at **1.13.8**, the first release maintained in this format. Releases
before it are documented on the
[releases page](https://github.com/horilla/horilla-crm/releases) and are not reproduced
here — they predate this convention and back-filling them would misrepresent how they
were recorded at the time.

Each released version corresponds to a git tag of the same name (bare semver, no `v`
prefix) and to the Docker tag `horilla/horilla-crm:<version>`. `horilla/__version__.py`
is the single source of truth for the **whole CRM product** version (not only the
`horilla/` package directory); the release workflow refuses to publish an image whose
tag disagrees with it. See [docs/versioning.md](docs/versioning.md).

Horilla CRM also versions its applications independently — each app carries its own
`__version__.py`, surfaced together by `horilla/utils/version.py`. Those app versions
move on their own cadence and are not tracked in this file.

## [Unreleased]

<!--
Add entries here as you merge, under the headings below. Drop any heading you
do not use. At release time, rename this section to the new version with its
date and open a fresh Unreleased above it.

### Breaking      — requires action from an existing installation before or on upgrade
### Added         — new features
### Changed       — changes to existing behaviour
### Deprecated    — soon-to-be-removed features
### Removed        — features removed in this release
### Fixed         — bug fixes
### Security      — vulnerabilities fixed; link the advisory and credit the reporter
-->

## [1.17.0] — 2026-10-23

### Added

- Mobile: optional phone mode under `/m/` with Records, Today, log activity,
  and Agenda. CRM models opt in from `mobile.py`.
- Generics: group-by bulk actions, matching the list view.
- Core: recycle bin **No expiry**; edit and delete dated exchange rates.

### Changed

- Generics: **Expand All** opens group rows in the viewport and continues as
  the user scrolls, including nested groups one level at a time.
- Activity: `OWNER_FIELDS` includes `participants` and `meeting_host`.
- Auth: a signed-out HTMX request gets **204** and `HX-Redirect` to login.
- Calendar: the grid rebuilds after a reload; toggling Google sync to its
  current state warns instead of saving again.
- Meeting: admin and user actions require integration to be enabled.
- Booking: users with only view-own access see My Bookings and their meeting
  activities.
- Cadences: report and navbar require `cadences.view_cadence`.
- CRM: related forms require change access on the parent record. Scoring
  rules require view permission. List rows show five actions.

### Fixed

- Core: Horilla 404 for `Http404`; circular role hierarchy; the last
  superuser cannot be removed from a stale page.
- Calls: access and provider changes are blocked when integration is already
  disabled.
- Mail: Test Mail on a deleted server shows the missing-record message.
- Reports: Excel export converts lazy field labels to strings.
- Approvals: Edit Details follows the edit policy, and the detail page stays
  after a reload.
- Dashboard: **Set to Default** is hidden when the home layout already matches.

## [1.15.3] — 2026-10-09

### Added

- Mail: generic **Inbox** for fetched incoming mail (preview and row actions).
- CRM: Email-to-Record creates **Contacts** as well as Leads via Inbox.
- Calendar: **Team members** filter (user picker), **status** filter, filtered
  members' unavailability in Team view.
- Automations: optional **edge-trigger-only** firing for on_update rules;
  Opportunity pre-save amount for amount-edge automations.
- Approvals: block the detail view while a record is pending approval.
- Reviews: **Create/Edit** triggers on review processes.

### Changed

- Calendar: rebuild custom calendars around module activities with event text
  colors; all-day activities are date-based and span whole days.
- Activity: related-record and custom calendar modules limited to opted-in
  models.
- Generics: forms can hide specific condition-row fields; condition Operator
  narrows by field type for content-type field names.
- Core: user-picker Select All selects every filtered user; Select2 on
  boolean/choice value fields; demo-data load when CRM modules are disabled.
- Extensions: LoginHistory uses `_inherit_model` instead of a monkey-patch.
- Booking: settings label renamed to **Booking Pages**.

### Fixed

- Generics: detail Next/Previous when disabled; duplicate breadcrumbs; hide
  non-editable detail/filter fields; cross-company users in owner dropdowns;
  bulk delete/export/update dispatch; GFK History diffs; export column
  selection (including empty selection).
- Calendar: same activity on both custom and standard calendars; all-day
  creation and navigation; action-button layout.
- Activity: Assigned To for all types; Related To save from Edit Details;
  related-record breadcrumbs.
- Automations: blank `created_by` when saving rules.
- Approvals: **Record owner** approver type in step matching.
- Calls: Call History tab gated on related-record access.
- Core: Super Users table scroll; Add User to Role modal title; role list
  description width.
- Utils: legacy table layout attributes through HTML sanitization.
- Jalali: History date-only vs DateTime timezone handling.

### Upgrading

```bash
docker pull horilla/horilla-crm:1.15.3
```

## [1.15.2] — 2026-10-02

### Added

- Generics: History tab **Show full text** toggle for full auditlog values
  (with Jalali formatting support).
- Generics: list views can opt out of the floating filter panel via
  `filter_panel_option`.
- Calendar: **Color by Type / Status** sidebar toggle; **Open Related Record**
  on activity event popups.
- Core: Holidays tab search in Company Information; Horilla navbar on Import
  Data; Docker `wait_for_db` (reads host/port from Django settings); second-
  company demo fixtures.
- Settings nav descriptions for Cadence, Workflow Rules, Review and Approval
  Processes.

### Changed

- Generics: quick filters work across view types; empty/stale filter rows are
  not rendered; detail field visibility can be scoped per record variant;
  preserve return URL after Edit All Fields.
- Custom Fields: hooks and extensions reorganized into `hooks/` and
  `extensions/` packages.
- Automations: schedule field order and clearer Run Time help text.
- Notifications: Channels push failures no longer break `Notification.save`;
  API nests a slim user serializer for sender/user details.
- CRM: opportunity owners can manage their own team without extra admin
  permissions; record edit actions default to the single-step form; company
  edit defaults to single-step.

### Fixed

- Calendar: Google credentials form validation errors; OAuth callback state
  harden (also Meeting Zoom/Teams); Google push skipped under `manage.py test`.
- Activity: Related To access/visibility; Add Column no longer offers
  unrelated fields.
- Calls: Object Call Log list no longer 500s when `object_id` is missing.
- Process: hide review jobs not assigned to the current user.
- CRM: forecast empty states, navbar, Go To Forecast Type links, and
  `#mainContent` on permission-denied.
- Generics: History tab readability/theming and stale no-op diffs; user-chip
  arrow uses primary theme color.
- Core: responsive role-members table height.

### Upgrading

```bash
docker pull horilla/horilla-crm:1.15.2
```

## [1.15.1] — 2026-09-25

### Added

- Generics: bulk **Edit Details** save on the record detail tab (replacing per-field
  pencil inline edit), with extension seams for Custom Fields, Duplicates, Approvals,
  and Jalali parsing.
- Generics: **Oldest First** list view type in the navbar.
- Form Layouts: offer a saved layout as an opt-in **Custom Layout** form mode on
  create and edit (alongside the default form).

### Changed

- Generics: `form_mode` replaces hardcoded multi/single-step URL switchers;
  request-cache field and per-row permission lookups; bulk export uses a hook instead
  of a global QuerySet patch; skip no-op detail/edit-all-fields saves.
- Calls and Process Builder: list-view action/visibility monkey patches replaced with
  MixinExtensions.
- Field Requirements: form overrides via the FormExtension pre-compose hook.

### Fixed

- Lead assignment rules keyed on custom fields now match on **create** (atomic
  `form_valid` so `save_m2m` completes before `on_commit`).
- Core: bulk field-permission queries memoized per request; permission messages use
  model verbose names.
- CRM: scoring `compute_score()` O(1) queries; Lead Delete for full permission;
  booking meeting link on Activity; full-permission Lead Owner and activity tabs.
- Booking: ShiftHour break windows in slots; public date-strip navigation; Join links.
- Mail: outgoing mail no longer picks an unrelated configuration.
- Meeting: Teams guest email display and real Graph errors.
- Activity: TypeError when sending meeting invite emails.
- Automations: scheduled trigger date / Run Time comparison.

### Upgrading

```bash
docker pull horilla/horilla-crm:1.15.1
```

## [1.15.0] — 2026-09-18

### Added

- **Form Layouts app** — administrators can choose, per company, which fields appear on
  the Lead and Opportunity create forms and in what order. Once a layout is saved, the
  create button opens a trimmed single-page form; edit forms are unchanged.
- Extension: `_inherit_mixin`, base-class targeting, pre-compose hooks, and
  `detail_section` composition for stacked view/form/filter extensions.

### Changed

- Custom Fields, Cadences, and Duplicates use real View/Form/Filter extensions instead
  of runtime monkey-patches.
- Related-list and history tabs reuse parent/ContentType lookups; kanban/detail
  pipelines attach `related_obj` for domain stages; per-company settings cache for
  currency and calendar/meeting/calls integration; public links use `SITE_URL`.

### Fixed

- Dashboard chart container resize after HTMX swap; Activity event due-date false
  error; Mail backend issue #39; sub-sidebar replacement when switching main
  sections; Docker Compose starts Celery only after migrations.

### Upgrading

```bash
docker pull horilla/horilla-crm:1.15.0
```

## [1.13.8] — 2026-09-05

### Added

- **Field Requirements app** — administrators can configure required and optional fields
  per company for supported CRM models such as Leads and Opportunities.
- Granted-access permission framework: users explicitly granted access to a record can
  act on it according to their assigned permissions without being the owner.
- Opportunity Team permissions gain dedicated read, edit and owner-level handling.
- Shared UI components: My Settings shell, empty-state components, active toggle.

### Changed

- Streaming-based CSV, XLSX and PDF exports.
- Database indexes added on frequently filtered and grouped fields; forecast period
  matching optimised; company list cached.

### Fixed

- Forecast pagination, history rendering, authentication fixes, and Exotel and Outlook
  integration error handling.

### Upgrading

```bash
docker pull horilla/horilla-crm:1.13.8
```

[Unreleased]: https://github.com/horilla/horilla-crm/compare/1.15.1...HEAD
[1.15.1]: https://github.com/horilla/horilla-crm/releases/tag/1.15.1
[1.15.0]: https://github.com/horilla/horilla-crm/releases/tag/1.15.0
[1.13.8]: https://github.com/horilla/horilla-crm/releases/tag/1.13.8
