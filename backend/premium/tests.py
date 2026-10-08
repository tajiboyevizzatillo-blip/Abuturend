from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Subject
from gamification.models import Badge
from practice.models import PracticeSession
from premium.models import Subscription, SubscriptionPlan
from premium.services import activate_plan
from questions.models import Question, QuestionOption

User = get_user_model()


class PremiumApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student1", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.free = SubscriptionPlan.objects.create(
            code="free-trial",
            tier=SubscriptionPlan.Tier.FREE,
            name_uz="Bepul",
            price_uzs=0,
            max_sessions_per_day=1,
        )
        self.pro = SubscriptionPlan.objects.create(
            code="pro-monthly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        q = Question.objects.create(
            subject=self.subject, text_uz="2+2?", status=Question.Status.PUBLISHED
        )
        QuestionOption.objects.create(question=q, text_uz="4", is_correct=True, sort_order=0)
        QuestionOption.objects.create(question=q, text_uz="3", is_correct=False, sort_order=1)
        self.client.force_login(self.user)

    def _start(self):
        return self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": 1, "mode": "practice"},
            format="json",
        )

    # ---- abandoning an in-progress session ---------------------------

    def _start_exam(self):
        return self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": 1, "mode": "exam"},
            format="json",
        )

    def test_abandon_marks_session_abandoned(self):
        session = self._start_exam().data
        res = self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        stored = PracticeSession.objects.get(pk=session["id"])
        self.assertEqual(stored.status, PracticeSession.Status.ABANDONED)
        self.assertIsNotNone(stored.finished_at)

    def test_abandon_does_not_score_or_report(self):
        """Abandoning is not finishing: no score and no report."""
        session = self._start_exam().data
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        stored = PracticeSession.objects.get(pk=session["id"])
        self.assertEqual(stored.correct_answers, 0)
        # The report stays closed for an abandoned attempt.
        res = self.client.get(f"/api/sessions/{session['id']}/report/")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        # And it does not count toward the statistics summary.
        summary = self.client.get("/api/stats/summary/")
        self.assertEqual(summary.data["total_finished"], 0)

    def test_abandon_does_not_unlock_badges(self):
        """A walked-away attempt must not earn gamification progress."""
        # The badge that only needs a finished session.
        Badge.objects.get_or_create(
            code="first-steps",
            defaults={"name_uz": "Birinchi qadam", "icon": "1"},
        )
        self.client.post(
            "/api/gamification/badges/check/", {}, format="json"
        )
        before = self.user.gamification_badges.count()

        session = self._start_exam().data
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.client.post(
            "/api/gamification/badges/check/", {}, format="json"
        )
        self.assertEqual(self.user.gamification_badges.count(), before)

    def test_abandon_still_consumes_the_daily_slot(self):
        """Documented behaviour: the questions were already served.

        Refunding the slot would let a free user view unlimited papers without
        answering one, which is what the daily limit exists to prevent.
        """
        from premium.services import remaining_sessions_today, sessions_started_today

        before_remaining = remaining_sessions_today(self.user)
        session = self._start_exam().data
        self.assertEqual(sessions_started_today(self.user), 1)
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.assertEqual(sessions_started_today(self.user), 1)
        self.assertEqual(
            remaining_sessions_today(self.user), before_remaining - 1
        )

    def test_abandon_frees_the_stuck_in_progress_session(self):
        """The original bug: no way to clear a session you cannot finish."""
        session = self._start_exam().data
        # current is refused while in progress only after it is terminal.
        self.assertEqual(
            self.client.get(f"/api/sessions/{session['id']}/current/").status_code,
            status.HTTP_200_OK,
        )
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.assertEqual(
            self.client.get(f"/api/sessions/{session['id']}/current/").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_abandoned_session_cannot_be_answered(self):
        session = self._start_exam().data
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        option = QuestionOption.objects.filter(question__subject=self.subject).first()
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": option.question_id, "option_id": option.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_abandon_twice_conflicts(self):
        session = self._start_exam().data
        self.client.post(f"/api/sessions/{session['id']}/abandon/")
        res = self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_abandon_after_finish_conflicts(self):
        session = self._start_exam().data
        self.client.post(f"/api/sessions/{session['id']}/finish/")
        res = self.client.post(f"/api/sessions/{session['id']}/abandon/")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        stored = PracticeSession.objects.get(pk=session["id"])
        self.assertEqual(stored.status, PracticeSession.Status.FINISHED)

    def test_abandon_only_own_session(self):
        other = User.objects.create_user(
            username="intruder", password="Passw0rd!", role=User.Role.STUDENT
        )
        session = PracticeSession.objects.create(
            user=other,
            subject=self.subject,
            mode=PracticeSession.Mode.EXAM,
            question_count=1,
        )
        res = self.client.post(f"/api/sessions/{session.id}/abandon/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        session.refresh_from_db()
        self.assertEqual(session.status, PracticeSession.Status.IN_PROGRESS)

    def test_plans_are_public(self):
        res = self.client.get("/api/premium/plans/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(res.data[0]["code"], "free-trial")

    def test_subscription_status_without_plan(self):
        res = self.client.get("/api/premium/subscription/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_premium"])
        self.assertIsNone(res.data["plan"])
        self.assertEqual(res.data["remaining_sessions_today"], 3)

    def test_subscribe_free_activates(self):
        res = self.client.post(
            "/api/premium/subscribe/", {"plan_code": "free-trial"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # The plan activates, but the free tier is not a paid entitlement:
        # is_premium reflects the tier, so it stays False. Treating "owns a
        # Subscription row" as premium would unlock every PRO-only feature for
        # a user who never paid.
        self.assertFalse(res.data["is_premium"])
        self.assertTrue(res.data["plan"]["is_active"])

    def test_paid_tier_reports_premium(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.pro,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30),
        )
        res = self.client.get("/api/premium/subscription/")
        self.assertTrue(res.data["is_premium"])

    def test_free_plan_with_unlimited_sessions_is_not_premium(self):
        """A free plan may not widen the daily quota by declaring it unlimited."""
        unlimited_free = SubscriptionPlan.objects.create(
            code="free-unlimited",
            tier=SubscriptionPlan.Tier.FREE,
            name_uz="Bepul cheksiz",
            price_uzs=0,
            max_sessions_per_day=None,
        )
        Subscription.objects.create(
            user=self.user,
            plan=unlimited_free,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30),
        )
        res = self.client.get("/api/premium/subscription/")
        self.assertFalse(res.data["is_premium"])
        # ...and the default free cap still applies.
        self.assertEqual(res.data["remaining_sessions_today"], 3)

    def test_free_plan_is_not_advertised_as_unlimited(self):
        """The plan catalogue must not promise what the backend will refuse."""
        unlimited_free = SubscriptionPlan.objects.create(
            code="free-unlimited",
            tier=SubscriptionPlan.Tier.FREE,
            name_uz="Bepul cheksiz",
            price_uzs=0,
            max_sessions_per_day=None,
        )
        pro_unlimited = SubscriptionPlan.objects.create(
            code="pro-unlimited",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.assertFalse(unlimited_free.unlimited_sessions)
        self.assertTrue(pro_unlimited.unlimited_sessions)

        res = self.client.get("/api/premium/plans/")
        by_code = {p["code"]: p for p in res.data}
        self.assertFalse(by_code["free-unlimited"]["unlimited_sessions"])
        self.assertTrue(by_code["pro-unlimited"]["unlimited_sessions"])

    def test_subscribe_paid_requires_gateway(self):
        res = self.client.post(
            "/api/premium/subscribe/", {"plan_code": "pro-monthly"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_subscribe_unknown_plan_rejected(self):
        res = self.client.post(
            "/api/premium/subscribe/", {"plan_code": "nope"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_free_limit_blocks_session(self):
        for _ in range(3):
            res = self._start()
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        res = self._start()
        self.assertEqual(res.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertTrue(res.data["premium_required"])
        self.assertEqual(res.data["remaining_sessions_today"], 0)

    def test_subscribed_free_plan_applies_its_limit(self):
        self.client.post(
            "/api/premium/subscribe/", {"plan_code": "free-trial"}, format="json"
        )
        res = self._start()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        res = self._start()
        self.assertEqual(res.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_premium_unlimited(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.pro,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30),
        )
        for _ in range(5):
            res = self._start()
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_subscribe_extends_active_plan(self):
        """A renewal of a *different* plan stacks after the current end date."""
        other = SubscriptionPlan.objects.create(
            code="pro-weekly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO haftalik",
            price_uzs=15_000,
            max_sessions_per_day=None,
        )
        first = Subscription.objects.create(
            user=self.user,
            plan=self.free,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=5),
        )
        activate_plan(self.user, other)
        latest = Subscription.objects.filter(user=self.user).order_by("-created_at").first()
        # Paid days must not be lost: the new period begins where the old ends.
        self.assertEqual(latest.starts_at, first.ends_at)

    def test_subscribe_same_plan_is_idempotent(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.free,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=5),
        )
        res = self.client.post(
            "/api/premium/subscribe/", {"plan_code": "free-trial"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["already_subscribed"])
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_subscribe_free_twice_does_not_stack_rows(self):
        for _ in range(3):
            self.client.post(
                "/api/premium/subscribe/", {"plan_code": "free-trial"}, format="json"
            )
        # Stacking free rows on the current end date made the entitlement
        # effectively permanent and grew the table without bound.
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)