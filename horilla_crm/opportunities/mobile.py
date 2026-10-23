"""
How opportunities show in the optional phone mode (``horilla.contrib.mobile``,
under ``/m/``): the row's name, line and fields, the status, and the fields
behind Call and Email.

Plain data, read by the mobile app when it is installed; this app opts the
model in with ``features=["mobile"]`` in ``registration.py``. The record
page's fields follow each user's choice on the desktop detail page.
"""

MOBILE_MODELS = {
    "Opportunity": {
        "title_field": "name",
        "email_field": "email",
        "status_field": "stage",
        "row_fields": ["account", "amount"],
        "search_fields": ["name"],
        "order": 4,
    },
}
