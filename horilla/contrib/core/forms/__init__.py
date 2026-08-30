"""
init file for core forms. This file can be used to import all the forms in the core app, so that they can be easily imported in other apps using from horilla.contrib.core.forms import *
"""

from horilla.contrib.core.forms.base import (
    FiscalYearForm,
    HolidayForm,
    BusinessHourForm,
    BusinessHourHolidayForm,
    RegionalFormattingForm,
    ChangePasswordForm,
)
from horilla.contrib.core.forms.shift_hour import ShiftHourForm

from horilla.contrib.core.forms.users import (
    UserFormClass,
    UserFormSingle,
    UserFormClassSingle,
    ChangeUserCompanyForm,
)

from horilla.contrib.core.forms.currency import (
    CurrencyForm,
    ConversionRateForm,
    DatedConversionRateForm,
)

from horilla.contrib.core.forms.company import (
    CompanyMultistepFormClass,
    CompanyFormClass,
    CompanyFormClassSingle,
)

from horilla.contrib.core.forms.field_requirement import (
    FieldRequirementForm,
    get_field_choices,
)

from horilla.contrib.core.forms.permission import (
    AddUsersToRoleForm,
    AddSuperUsersForm,
)

__all__ = [
    # Base forms
    "FiscalYearForm",
    "HolidayForm",
    "BusinessHourForm",
    "BusinessHourHolidayForm",
    "ShiftHourForm",
    "RegionalFormattingForm",
    "ChangePasswordForm",
    "ChangeUserCompanyForm",
    # Currency forms
    "CurrencyForm",
    "ConversionRateForm",
    "DatedConversionRateForm",
    # User forms
    "UserFormClass",
    "UserFormSingle",
    "UserFormClassSingle",
    # Company forms
    "CompanyMultistepFormClass",
    "CompanyFormClass",
    "CompanyFormClassSingle",
    # Field requirement forms
    "FieldRequirementForm",
    "get_field_choices",
    # Permission forms
    "AddUsersToRoleForm",
    "AddSuperUsersForm",
]
