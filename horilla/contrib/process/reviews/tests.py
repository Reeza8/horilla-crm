"""
Tests for the reviews app
"""

# Third-party imports (Django)
from types import SimpleNamespace

from django.test import TestCase

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local
from horilla.core.exceptions import ValidationError

# Local imports
from .models import ReviewCondition, ReviewJob, ReviewProcess, ReviewRule
from .utils import was_moved_to_pending_review


class ReviewTriggerTests(TestCase):
    """Review jobs follow the Create / Edit trigger settings."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        self.approver = User.objects.create_user(
            username="approver",
            email="approver@example.com",
            password="x",
            company=self.company,
        )
        self.lead_model = apps.get_model("leads", "Lead")
        self.status_model = apps.get_model("leads", "LeadStatus")
        self.status = self.status_model.objects.create(
            name="New", probability=10, company=self.company
        )
        self.content_type = HorillaContentType.objects.get_for_model(self.lead_model)

    def _process(self, **kwargs):
        defaults = {
            "title": "Lead review",
            "model": self.content_type,
            "review_fields": ["lead_company"],
            "company": self.company,
            "trigger_on_create": True,
            "trigger_on_edit": True,
            "created_by": self.approver,
            "updated_by": self.approver,
        }
        defaults.update(kwargs)
        process = ReviewProcess.objects.create(**defaults)
        rule = ReviewRule.objects.create(
            reviews=process,
            approver_type="user",
            company=self.company,
            created_by=self.approver,
            updated_by=self.approver,
        )
        rule.approver_users.add(self.approver)
        return process

    def _lead(self, **kwargs):
        defaults = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "lead_company": "Prospect",
            "lead_source": "website",
            "industry": "technology",
            "lead_status": self.status,
            "lead_owner": self.approver,
            "company": self.company,
        }
        defaults.update(kwargs)
        return self.lead_model.objects.create(**defaults)

    def _jobs(self, lead):
        return ReviewJob.all_objects.filter(
            content_type=self.content_type, object_id=lead.pk
        )

    def _approve(self, lead):
        job = self._jobs(lead).get()
        job.status = ReviewJob.STATUS_APPROVED
        job.additional_info = {
            "field_reviews": {"lead_company": {"status": ReviewJob.STATUS_APPROVED}}
        }
        job.save()
        return job

    def test_new_process_defaults_to_create_only(self):
        process = self._process(trigger_on_edit=ReviewProcess().trigger_on_edit)
        self.assertTrue(process.trigger_on_create)
        self.assertFalse(process.trigger_on_edit)

    def test_create_starts_review(self):
        self._process()
        lead = self._lead()
        self.assertEqual(self._jobs(lead).count(), 1)

    def test_create_ignored_when_create_trigger_off(self):
        self._process(trigger_on_create=False)
        lead = self._lead()
        self.assertEqual(self._jobs(lead).count(), 0)

    def test_edit_of_other_field_does_not_touch_review(self):
        self._process()
        lead = self._lead()
        job = self._approve(lead)

        lead.email = "other@example.com"
        lead.save()

        job.refresh_from_db()
        self.assertEqual(job.status, ReviewJob.STATUS_APPROVED)
        self.assertEqual(self._jobs(lead).count(), 1)

    def test_edit_of_reviewed_field_reopens_review(self):
        self._process()
        lead = self._lead()
        job = self._approve(lead)

        lead.lead_company = "Changed Co"
        lead.save()

        job.refresh_from_db()
        self.assertEqual(job.status, ReviewJob.STATUS_PENDING)
        self.assertEqual(job.review_fields_snapshot["lead_company"], "Changed Co")
        field_review = job.additional_info["field_reviews"]["lead_company"]
        self.assertEqual(field_review["status"], ReviewJob.STATUS_PENDING)
        self.assertEqual(len(job.additional_info["review_history"]), 1)

    def test_saving_without_changes_does_nothing(self):
        self._process()
        lead = self._lead()
        job = self._approve(lead)

        lead.save()

        job.refresh_from_db()
        self.assertEqual(job.status, ReviewJob.STATUS_APPROVED)

    def test_edit_ignored_when_edit_trigger_off(self):
        self._process(trigger_on_edit=False)
        lead = self._lead()
        job = self._approve(lead)

        lead.lead_company = "Changed Co"
        lead.save()

        job.refresh_from_db()
        self.assertEqual(job.status, ReviewJob.STATUS_APPROVED)

    def test_edit_only_process_skips_create_and_starts_on_edit(self):
        self._process(trigger_on_create=False)
        lead = self._lead()
        self.assertEqual(self._jobs(lead).count(), 0)

        lead.email = "other@example.com"
        lead.save()
        self.assertEqual(self._jobs(lead).count(), 0)

        lead.lead_company = "Changed Co"
        lead.save()
        self.assertEqual(self._jobs(lead).count(), 1)

    def test_update_fields_save_ignores_unsaved_reviewed_field(self):
        self._process()
        lead = self._lead()
        job = self._approve(lead)

        lead.lead_company = "Changed Co"
        lead.email = "other@example.com"
        lead.save(update_fields=["email"])

        job.refresh_from_db()
        self.assertEqual(job.status, ReviewJob.STATUS_APPROVED)

    def _criteria(self, process, status):
        return ReviewCondition.objects.create(
            reviews=process,
            field="lead_status",
            operator="exact",
            value=str(status.pk),
            company=self.company,
            created_by=self.approver,
            updated_by=self.approver,
        )

    def test_edit_of_criteria_field_starts_review(self):
        qualified = self.status_model.objects.create(
            name="Qualified", probability=50, company=self.company
        )
        self._criteria(self._process(), qualified)
        lead = self._lead()
        self.assertEqual(self._jobs(lead).count(), 0)

        lead.lead_status = qualified
        lead.save()

        self.assertEqual(self._jobs(lead).count(), 1)

    def test_edit_of_criteria_field_does_not_apply_when_edit_trigger_off(self):
        qualified = self.status_model.objects.create(
            name="Qualified", probability=50, company=self.company
        )
        self._criteria(self._process(trigger_on_edit=False), qualified)
        lead = self._lead()

        lead.lead_status = qualified
        lead.save()

        self.assertEqual(self._jobs(lead).count(), 0)

    def _moved(self, lead):
        return was_moved_to_pending_review(
            _thread_local.request, "leads", "lead", lead.pk
        )

    def test_edit_that_starts_review_is_flagged_for_the_detail_view(self):
        qualified = self.status_model.objects.create(
            name="Qualified", probability=50, company=self.company
        )
        self._criteria(self._process(), qualified)
        lead = self._lead()
        _thread_local.request = SimpleNamespace(session={})
        self.addCleanup(lambda: delattr(_thread_local, "request"))

        lead.email = "other@example.com"
        lead.save()
        self.assertFalse(self._moved(lead))

        lead.lead_status = qualified
        lead.save()
        self.assertTrue(self._moved(lead))

    def test_edit_that_reopens_approved_review_is_flagged(self):
        self._process()
        lead = self._lead()
        self._approve(lead)
        _thread_local.request = SimpleNamespace(session={})
        self.addCleanup(lambda: delattr(_thread_local, "request"))

        lead.email = "other@example.com"
        lead.save()
        self.assertFalse(self._moved(lead))

        lead.lead_company = "Changed Co"
        lead.save()
        self.assertTrue(self._moved(lead))

    def test_at_least_one_trigger_required(self):
        process = ReviewProcess(
            title="No trigger",
            model=self.content_type,
            review_fields=["lead_company"],
            company=self.company,
            trigger_on_create=False,
            trigger_on_edit=False,
        )
        with self.assertRaises(ValidationError):
            process.clean()

    def test_execute_display(self):
        process = ReviewProcess(trigger_on_create=True, trigger_on_edit=True)
        self.assertEqual(process.get_execute_display(), "Create and Edit")
        process.trigger_on_edit = False
        self.assertEqual(process.get_execute_display(), "Create only")
        process.trigger_on_create, process.trigger_on_edit = False, True
        self.assertEqual(process.get_execute_display(), "Edit only")
