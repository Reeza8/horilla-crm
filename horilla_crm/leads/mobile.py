"""
How leads show in the optional phone mode (``horilla.contrib.mobile``,
under ``/m/``): the row's name, line and fields, the status, and the fields
behind Call and Email.

Plain data, read by the mobile app when it is installed; this app opts the
model in with ``features=["mobile"]`` in ``registration.py``. The record
page's fields follow each user's choice on the desktop detail page.
"""

MOBILE_MODELS = {
    "Lead": {
        "title_field": "title",
        "subtitle_fields": ["first_name", "last_name"],
        "phone_fields": ["contact_number"],
        "email_field": "email",
        "status_field": "lead_status",
        "row_fields": ["lead_owner"],
        "search_fields": ["title", "first_name", "last_name", "lead_company"],
        "filter_fields": ["lead_source"],
        # Records opens on leads, then contacts, accounts, opportunities.
        "order": 1,
    },
}
