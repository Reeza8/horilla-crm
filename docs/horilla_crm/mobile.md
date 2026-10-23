# CRM on the phone (`mobile.py`)

Leads, contacts, accounts and opportunities show in the optional phone mode,
[`horilla.contrib.mobile`](../horilla/contrib/mobile/mobile.md), when that app
is installed. Each app opts its model in the way the phone app asks:

1. `features=[..., "mobile"]` for the model in the app's `registration.py`;
2. a `mobile.py` next to it with the display settings, as plain data. It
   never imports the mobile app, which loads it at startup only when it is
   installed.

Without the mobile app, both are inert: the feature registry keeps the
unknown feature name, and nothing reads `mobile.py`.

| Model | Row (title, line, fields) | Status | Call | Email | Search | Filters |
|-------|---------------------------|--------|------|-------|--------|---------|
| Lead (`leads/mobile.py`) | title; first and last name; owner | lead status | phone | email | title, first and last name, company | source |
| Contact (`contacts/mobile.py`) | full name; job title, owner | — | phone, secondary phone (asks which) | email | first and last name | source |
| Account (`accounts/mobile.py`) | name; industry, billing city | — | phone | — | name, billing city | type |
| Opportunity (`opportunities/mobile.py`) | name; account, amount | stage | — | email | name | — |

The Records tab lists them in that order (`order` 1 to 4): leads first.
Every model is also found by its email, and by any of its phone numbers
however they were typed.

The record page doesn't need settings here: its key fields and **All fields**
follow each user's choice on the desktop detail page, custom fields included.
The status changes on the phone through the desktop stage bar (lead status,
opportunity stage), with the same rules: converting a lead stays on the
desktop. See the [mobile app's docs](../horilla/contrib/mobile/mobile.md) for
every option.
