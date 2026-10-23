"""
How contacts show in the optional phone mode (``horilla.contrib.mobile``,
under ``/m/``): the row's name, line and fields, the status, and the fields
behind Call and Email.

Plain data, read by the mobile app when it is installed; this app opts the
model in with ``features=["mobile"]`` in ``registration.py``. The record
page's fields follow each user's choice on the desktop detail page.
"""

MOBILE_MODELS = {
    "Contact": {
        # No title field: a contact's name is its first and last name.
        "phone_fields": ["contact_number", "secondary_contact_number"],
        "email_field": "email",
        "row_fields": ["title", "contact_owner"],
        "search_fields": ["first_name", "last_name"],
        "filter_fields": ["contact_source"],
        "order": 2,
    },
}
