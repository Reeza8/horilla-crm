"""History tab RTL / Farsi overlays — no Horilla core or rtl.css edits."""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase


class HistoryTabRtlOverlayTests(SimpleTestCase):
    """Project overlays and history-rtl.css, kept off rtl.css / generics core."""

    def test_rtl_css_is_unchanged_by_history_rules(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "assets" / "css" / "rtl.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn("#history-main", css)
        self.assertNotIn("history-rtl.css", css)
        self.assertNotIn("history-filter-bar", css)

    def test_history_rtl_css_covers_filter_and_bidi(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "assets" / "css" / "history-rtl.css"
        ).read_text(encoding="utf-8")
        self.assertIn('[dir="rtl"] #history-main .history-filter-bar', css)
        self.assertNotIn("flex-direction: row-reverse", css)
        self.assertIn("unicode-bidi: isolate", css)

    def test_history_tab_css_expands_detail_pane(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "assets" / "css" / "history-tab.css"
        ).read_text(encoding="utf-8")
        self.assertIn("history-tab-expanded", css)
        self.assertIn("#detailHeaderCard", css)

    def test_rtl_assets_overlay_loads_history_stylesheet(self):
        html = render_to_string("inject_html/rtl_assets.html", {"LANGUAGE_BIDI": True})
        self.assertIn("assets/css/rtl.css", html)
        self.assertIn("assets/css/history-rtl.css", html)

    def test_history_tab_overlay_uses_localizable_phrases(self):
        text = (Path(settings.BASE_DIR) / "templates" / "history_tab.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("New {{ model }} created", text)
        self.assertIn("{% trans field %}", text)
        self.assertIn("LANGUAGE_BIDI", text)
        self.assertIn("history-filter-bar", text)
        self.assertIn("history-kv", text)
        self.assertIn("history_datetime", text)
        self.assertIn("{% load history_i18n %}", text)
        self.assertIn("history_is_date_field", text)
        self.assertIn("history-expand-btn", text)
        self.assertNotIn("sticky top-4", text)
        actor = (
            Path(settings.BASE_DIR)
            / "templates"
            / "partials"
            / "history_entry_actor.html"
        ).read_text(encoding="utf-8")
        self.assertIn('{% trans "by" %}', actor)

    def test_core_history_template_is_not_modified(self):
        text = (
            Path(settings.BASE_DIR)
            / "horilla"
            / "contrib"
            / "generics"
            / "templates"
            / "history_tab.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("history-filter-bar", text)
        self.assertIn('{% trans "New" %}', text)

    def test_persian_history_strings_exist(self):
        po = (
            Path(settings.BASE_DIR)
            / "horilla_crm"
            / "leads"
            / "locale"
            / "fa"
            / "LC_MESSAGES"
            / "django.po"
        ).read_text(encoding="utf-8")
        self.assertIn('msgid "by"', po)
        self.assertIn('msgstr "توسط"', po)
        self.assertIn('msgid "New %(model)s created"', po)
        self.assertIn('msgstr "%(model)s جدید ایجاد شد"', po)
        self.assertIn('msgid "Sender"', po)
        self.assertIn('msgstr "فرستنده"', po)
        self.assertIn('msgid "Expand"', po)
        self.assertIn('msgstr "بزرگ‌نمایی"', po)
        self.assertIn('msgid "Select date to filter"', po)
        self.assertIn('msgstr "تاریخ را برای فیلتر انتخاب کنید"', po)
        self.assertIn('msgid "Apply"', po)
        self.assertIn('msgstr "اعمال"', po)

    def test_history_filter_form_overlay_is_translated(self):
        text = (
            Path(settings.BASE_DIR)
            / "templates"
            / "partials"
            / "history_filter_form.html"
        ).read_text(encoding="utf-8")
        self.assertIn('{% trans "Select date to filter" %}', text)
        self.assertIn('{% trans "Filter" %}', text)
        self.assertIn('{% trans "Apply" %}', text)
        self.assertNotIn("form.filter_date.label_tag", text)
        self.assertIn("initHorillaJalaliInputs", text)

    def test_history_tab_overlay_is_the_resolved_template(self):
        template = get_template("history_tab.html")
        self.assertIn("templates", Path(template.origin.name).parts)
        self.assertNotIn("contrib", Path(template.origin.name).parts)


class HistoryDatetimeShamsiTests(SimpleTestCase):
    """Persian UI history timestamps must render as Jalali."""

    def test_persian_history_datetime_uses_shamsi_year(self):
        from datetime import datetime

        from django.utils.translation import override

        from horilla_crm.leads.templatetags.history_i18n import history_datetime

        with override("fa"):
            text = str(history_datetime(datetime(2026, 8, 19, 15, 7, 13)))
        self.assertIn("۱۴۰۵", text)
        self.assertNotIn("1405", text)
        self.assertNotIn("2026", text)
        self.assertNotIn("بعد از ظهر", text)
        self.assertNotIn("قبل از ظهر", text)
        self.assertNotIn("PM", text)
        self.assertNotIn("AM", text)
        self.assertNotRegex(text, r"[0-9]:[0-9]")

    def test_twelve_hour_format_renders_as_24_hour_without_ampm(self):
        from datetime import datetime
        from types import SimpleNamespace

        from django.utils.translation import override

        from horilla_crm.leads.templatetags.history_i18n import _format_shamsi

        user = SimpleNamespace(
            date_time_format="%Y-%m-%d %I:%M:%S %p",
            time_zone=None,
        )
        with override("fa"):
            text = str(
                _format_shamsi(
                    datetime(2026, 8, 19, 20, 1, 59), user=user, company=None
                )
            )
        self.assertIn("۱۴۰۵", text)
        self.assertIn("۲۰:۰۱", text)
        self.assertNotIn("20:01", text)
        self.assertNotIn("۲۰:۰۱:۵۹", text)
        self.assertNotIn("20:01:59", text)
        self.assertNotIn("08:01:59", text)
        self.assertNotIn("بعد از ظهر", text)
        self.assertNotIn("PM", text)

    def test_date_only_uses_persian_digits(self):
        from datetime import date

        from django.utils.translation import override

        from horilla_crm.leads.templatetags.history_i18n import history_datetime

        with override("fa"):
            text = str(history_datetime(date(2026, 8, 19)))
        self.assertIn("۱۴۰۵", text)
        self.assertNotIn("1405", text)

    def test_localized_persian_gregorian_converts_to_shamsi(self):
        from django.utils.translation import override

        from horilla_crm.leads.templatetags.history_i18n import history_datetime

        with override("fa"):
            text = str(history_datetime("19 اوت 2026، ساعت 8:27"))
        self.assertIn("۱۴۰۵", text)
        self.assertNotIn("اوت", text)
        self.assertNotIn("2026", text)
        self.assertNotIn("ساعت", text)
        self.assertIn("۰۸:۲۷", text)
        self.assertNotIn("08:27", text)
        self.assertNotIn("۰۸:۲۷:۰۰", text)

    def test_history_is_date_field_matches_persian_start_date_label(self):
        from horilla_crm.leads.templatetags.history_i18n import history_is_date_field

        self.assertTrue(history_is_date_field(None, "تاریخ شروع"))
        self.assertTrue(history_is_date_field(None, "به‌روزرسانی شده در"))
        self.assertFalse(history_is_date_field(None, "وضعیت"))
