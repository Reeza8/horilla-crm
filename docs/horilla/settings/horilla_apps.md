# `horilla_apps.py`

## 🎯 Purpose

This file extends `INSTALLED_APPS` beyond what is defined in `base.py`.

It does:
- imports `INSTALLED_APPS` from `horilla.settings.base`
- appends Horilla/CRM app packages (accounts, contacts, leads, etc.)

## What it adds (current)

It extends with:
- `horilla_crm.accounts`
- `horilla_crm.contacts`
- `horilla_crm.leads`
- `horilla_crm.scoring_rules`
- `horilla_crm.campaigns`
- `horilla_crm.opportunities`
- `horilla_crm.forecast`
- `booking`

`booking` is documented in [../contrib/booking/booking.md](../contrib/booking/booking.md).

## When it runs

It is loaded automatically when:
- Django imports `horilla.settings.__init__`
- that file imports `horilla.settings.horilla_apps`
