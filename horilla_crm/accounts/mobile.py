"""
How accounts show in the optional phone mode (``horilla.contrib.mobile``,
under ``/m/``): the row's name, line and fields, the status, and the fields
behind Call and Email.

Plain data, read by the mobile app when it is installed; this app opts the
model in with ``features=["mobile"]`` in ``registration.py``. The record
page's fields follow each user's choice on the desktop detail page.
"""

MOBILE_MODELS = {
    "Account": {
        "title_field": "name",
        "phone_fields": ["contact_number"],
        "row_fields": ["industry", "billing_city"],
        "search_fields": ["name", "billing_city"],
        "filter_fields": ["account_type"],
        "order": 3,
    },
}
