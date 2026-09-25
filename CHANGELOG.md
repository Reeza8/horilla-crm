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
