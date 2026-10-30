# Horilla Theme App

This app manages dynamic color themes in Horilla and applies them per company.

## What This App Does

- Stores complete Tailwind color palettes in the database.
- Lets each company select a theme.
- Applies selected colors dynamically in UI templates.
- Injects theme config scripts/styles into `index.html` and `login.html`.
- Seeds built-in themes after initial migration.

## App Startup (`apps.py`)

`ThemeConfig` extends `AppLauncher` and auto-imports:

- `menu`
- `signals`
- `registration`

This ensures menu registration, signal handlers, and HTML asset registration are loaded when the server starts.

## Settings Menu Registration (`menu.py`)

`ThemeSettings` is registered with `@settings_menu.register` to show Theme Manager in Settings.

- Title: uses `ThemeConfig.verbose_name` (Theme Manager)
- Icon: `/theme/assets/icons/theme.svg`
- Item URL: `theme:color_theme_view`

## Theme Models (`models.py`)

### `HorillaColorTheme`

Stores a full color system:

- Primary: `primary_50` ... `primary_900`
- Dark: `dark_25` ... `dark_600`
- Secondary: `secondary_50` ... `secondary_900`
- Surface: `surface` (supports `#RRGGBB` or `#RRGGBBAA`)

Also includes:

- `is_default` to mark login/default theme.
- Atomic save logic to enforce only one default theme.
- `get_default_theme()` helper for fallback.

### `CompanyTheme`

Stores selected theme per company using FK to `HorillaColorTheme`.

- `get_theme_for_company(company)` returns:
  - company theme, if set
  - otherwise default fallback theme

## HTML Injection Registration (`registration.py`)

Registers template fragments into `head_end` slot:

- `inject_html/tailwind_dynamic_config.html` (main app pages)
- `inject_html/tailwind_dynamic_config_login.html` (login page only)

## Dynamic Tailwind Injection

### Main App (`tailwind_dynamic_config.html`)

- Reads active company theme from request context:
  `request.active_company.companytheme_set.first.theme`
- Builds `window.tailwind.config.theme.colors` dynamically.
- Sets CSS variables for app-specific UI parts (split-view, timeline, calendar, etc.).
- Applies SVG filter/hue adjustment based on selected primary color.

### Login (`tailwind_dynamic_config_login.html`)

- First checks `localStorage.lastActiveTheme` (set during logout).
- Falls back to default theme provided by login context signal.
- Injects same dynamic Tailwind color map for login page.

## Template Integration Points

### `templates/index.html`

Uses registered head-end templates:

```django
{% load_registered_html "head_end" as head_end_html %}
{% for tpl in head_end_html %} {% include tpl %} {% endfor %}
```

### `templates/login.html`

Uses page-scoped head-end templates:

```django
{% load_registered_html "head_end" "login" as head_end_html %}
{% for tpl in head_end_html %} {% include tpl %} {% endfor %}
```

## Signals (`signals.py`)

### Built-in themes seeding

- `create_default_themes` exists to seed `THEMES_DATA` when the theme app’s **initial** migration runs; the **`@receiver(post_migrate, ...)` decorator is currently commented out** in `signals.py`.
- Use the management command **`create_default_themes`** (`horilla/contrib/theme/management/commands/create_default_themes.py`) to seed palettes in environments where automatic post-migrate seeding is not wired.

### `pre_logout_signal` -> save active theme to localStorage payload

- Reads current company theme.
- Returns `("lastActiveTheme", theme_data_dict)` for frontend persistence.

### `pre_login_render_signal` -> add login theme context

- Adds `context["theme"] = HorillaColorTheme.get_default_theme()`.
- Lets login page render with default/custom configured theme.

## Dark theme

`static/assets/css/dark.css` applies the active theme colours to outline buttons and badges, as well as filled primary controls.

## Data Source for Built-in Themes

`utils.py` contains `THEMES_DATA`, a list of predefined palettes used for initial seeding.

## Typical Flow

1. Server starts -> app auto-imports `menu`, `signals`, `registration`.
2. After first migrate **or** running **`create_default_themes`** → default `HorillaColorTheme` rows exist.
3. User opens app -> company theme is injected into Tailwind config.
4. User logs out -> active theme stored as `lastActiveTheme`.
5. Login page loads -> theme restored from localStorage or default theme.
