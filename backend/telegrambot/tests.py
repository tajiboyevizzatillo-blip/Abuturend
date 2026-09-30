from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Subject
from questions.models import Question

from . import services

User = get_user_model()


class TelegramServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student1",
            password="Passw0rd!",
            role=User.Role.STUDENT,
        )
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.question = Question.objects.create(
            subject=self.subject,
            text_uz="2+2 nechaga teng?",
            explanation_uz="4 ga teng",
            status=Question.Status.DRAFT,
            created_by=None,
        )

    def test_new_user_text_contains_username(self):
        text = services.new_user_text(self.user)
        self.assertIn("student1", text)
        self.assertIn("Abituriyent", text)

    def test_question_submitted_text_contains_subject(self):
        author = User.objects.create_user(
            username="teach1", password="Passw0rd!", role=User.Role.TEACHER
        )
        self.question.created_by = author
        self.question.save()
        text = services.question_submitted_text(self.question)
        self.assertIn("Matematika", text)
        self.assertIn("teach1", text)
        self.assertIn("2+2", text)

    def test_daily_stats_text_contains_today(self):
        text = services.daily_stats_text()
        self.assertIn(timezone.localdate().strftime("%d.%m.%Y"), text)
        self.assertIn("Abiturend", text)

    def test_leaderboard_text_empty_state(self):
        text = services.leaderboard_text()
        self.assertIn("Reyting", text)

    def test_status_text_contains_counts(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="s2", password="Passw0rd!", role=User.Role.STUDENT
        )
        text = services.status_text()
        self.assertIn("Savollar", text)
        self.assertIn("Foydalanuvchilar", text)

    def test_send_message_noop_when_unconfigured(self):
        results = services.send_message("hello")
        self.assertEqual(results, [])

    def test_is_configured_false_by_default(self):
        with self.settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID=""):
            self.assertFalse(services.is_configured())

    def test_onboarding_completed_text_contains_plan_details(self):
        from datetime import timedelta

        from onboarding.models import OnboardingPlan, OnboardingProfile

        profile = OnboardingProfile.objects.create(
            user=self.user,
            exam_date=timezone.localdate() + timedelta(days=30),
            daily_minutes=90,
            level="middle",
            completed=True,
        )
        profile.subjects.add(self.subject)
        OnboardingPlan.objects.create(
            profile=profile,
            start_date=timezone.localdate(),
            days=[{"day": 1, "date": timezone.localdate().isoformat(), "items": []}],
            weak_subject_ids=[self.subject.id],
        )
        text = services.onboarding_completed_text(profile)
        self.assertIn("student1", text)
        self.assertIn("Matematika", text)
        self.assertIn("90", text)
        # HTML-parsed Telegram text: the apostrophe is escaped.
        self.assertIn("rta", text)

    def test_onboarding_completed_text_without_plan(self):
        from onboarding.models import OnboardingProfile

        profile = OnboardingProfile.objects.create(user=self.user)
        text = services.onboarding_completed_text(profile)
        self.assertIn("student1", text)
        self.assertNotIn("Reja:", text)


class TelegramWebhookTests(TestCase):
    def _post(self, text, chat_id="5458715260", secret="test-secret"):
        from django.test import Client

        c = Client()
        return c.post(
            "/webhooks/telegram/",
            data=f'{{"message":{{"chat":{{"id":"{chat_id}"}},"text":"{text}"}}}}',
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret,
            SERVER_NAME="localhost",
        )

    @override_settings(
        TELEGRAM_WEBHOOK_SECRET="test-secret",
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHAT_ID="",
    )
    def test_unauthorized_secret_rejected(self):
        resp = self._post("/id", secret="wrong")
        self.assertEqual(resp.status_code, 401)

    @override_settings(
        TELEGRAM_WEBHOOK_SECRET="test-secret",
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHAT_ID="5458715260",
    )
    def test_unknown_command_greeted(self):
        resp = self._post("/bogus")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

    @override_settings(
        TELEGRAM_WEBHOOK_SECRET="test-secret",
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_CHAT_ID="5458715260",
    )
    def test_non_admin_chat_ignored(self):
        resp = self._post("/id", chat_id="999")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})