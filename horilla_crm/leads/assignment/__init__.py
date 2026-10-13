"""
Lead assignment-rule logic that does not depend on a request or a form.

* ``evaluation`` - compare criteria against plain data (a saved lead or a
  form's ``cleaned_data``), including "not known yet" handling for forms.
* ``pool`` - active rules, the people a condition can assign to, and the
  least-loaded pick.
* ``notify`` - the email / in-app notification senders for an assignment.

The post-save engine in ``horilla_crm.leads.signals`` and the "Apply
assignment rule" option on the lead forms both use these modules, so the two
paths can not drift apart.
"""
