from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Subject, Topic
from onboarding.models import OnboardingPlan, OnboardingProfile
from onboarding.plan import (
    LEVEL_FACTORS,
    MAX_QUESTIONS_PER_ITEM,
    daily_question_budget,
)
from practice.models import PracticeAnswer, PracticeSession
from questions.models import Question, QuestionOption
from universities.models import Direction, University

User = get_user_model()


def _question(subject, text):
    q = Question.objects.create(
        subject=subject,
        text_uz=text,
        status=Question.Status.PUBLISHED,
    )
    QuestionOption.objects.create(question=q, text_uz="A", is_correct=True, sort_order=0)
    QuestionOption.objects.create(question=q, text_uz="B", is_correct=False, sort_order=1)
    return q


class OnboardingBaseTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student1", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.math = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.lang = Subject.objects.create(name_uz="Ona tili", slug="ona-tili")
        for i in range(1, 4):
            Topic.objects.create(
                subject=self.math,
                name_uz=f"Bo'lim {i}",
                slug=f"bolim-{i}",
                sort_order=i,
            )
        self.uni = University.objects.create(name_uz="Milliy universitet", slug="milliy")
        self.direction = Direction.objects.create(
            university=self.uni, name_uz="Axborot texnologiyalari", code="606.1"
        )
        self.direction.subjects.add(self.math)
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        data = {
            "subjects": [self.math.id],
            "daily_minutes": 60,
            "level": OnboardingProfile.Level.BEGINNER,
        }
        data.update(overrides)
        return data


class OnboardingPermissionTests(OnboardingBaseTests):
    def test_get_requires_login(self):
        self.client.logout()
        res = self.client.get("/api/onboarding/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_submit_requires_login(self):
        self.client.logout()
        res = self.client.post("/api/onboarding/", self._payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_plan_and_skip_require_login(self):
        self.client.logout()
        self.assertEqual(
            self.client.get("/api/onboarding/plan/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post("/api/onboarding/skip/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_user_only_sees_own_profile(self):
        other = User.objects.create_user(username="student2", password="Passw0rd!")
        OnboardingProfile.objects.create(user=other, completed=True)
        res = self.client.get("/api/onboarding/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Another user's completed profile must not mark this one as onboarded.
        self.assertTrue(res.data["needs_onboarding"])
        self.assertFalse(res.data["completed"])
        # GET lazily creates an empty profile for the caller only.
        profile = OnboardingProfile.objects.get(user=self.user)
        self.assertFalse(profile.completed)
        self.assertFalse(profile.skipped)


class OnboardingStatusTests(OnboardingBaseTests):
    def test_status_starts_incomplete(self):
        res = self.client.get("/api/onboarding/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["needs_onboarding"])
        self.assertFalse(res.data["completed"])
        self.assertFalse(res.data["skipped"])
        self.assertFalse(res.data["has_plan"])

    def test_skip_marks_profile_and_stops_redirect(self):
        res = self.client.post("/api/onboarding/skip/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        profile = OnboardingProfile.objects.get(user=self.user)
        self.assertTrue(profile.skipped)
        self.assertFalse(profile.needs_onboarding())
        status_res = self.client.get("/api/onboarding/")
        self.assertFalse(status_res.data["needs_onboarding"])

    def test_plan_404_before_wizard(self):
        res = self.client.get("/api/onboarding/plan/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class OnboardingValidationTests(OnboardingBaseTests):
    def test_exam_date_in_past_rejected(self):
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        res = self.client.post(
            "/api/onboarding/", self._payload(exam_date=past), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exam_date", res.data)

    def test_exam_date_today_rejected(self):
        today = timezone.localdate().isoformat()
        res = self.client.post(
            "/api/onboarding/", self._payload(exam_date=today), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_at_least_one_subject_required(self):
        res = self.client.post("/api/onboarding/", self._payload(subjects=[]), format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("subjects", res.data)

    def test_duplicate_subjects_rejected(self):
        res = self.client.post(
            "/api/onboarding/",
            self._payload(subjects=[self.math.id, self.math.id]),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_daily_minutes_bounds(self):
        for value in (14, 481):
            res = self.client.post(
                "/api/onboarding/", self._payload(daily_minutes=value), format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_level_rejected(self):
        res = self.client.post(
            "/api/onboarding/", self._payload(level="expert"), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_subject_rejected(self):
        inactive = Subject.objects.create(
            name_uz="Nofaol fan", slug="nofaol-fan", is_active=False
        )
        res = self.client.post(
            "/api/onboarding/", self._payload(subjects=[inactive.id]), format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class OnboardingPlanTests(OnboardingBaseTests):
    def test_submit_creates_profile_and_plan(self):
        future = (timezone.localdate() + timedelta(days=40)).isoformat()
        res = self.client.post(
            "/api/onboarding/",
            self._payload(
                direction=self.direction.id,
                subjects=[self.math.id, self.lang.id],
                exam_date=future,
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        profile = OnboardingProfile.objects.get(user=self.user)
        self.assertTrue(profile.completed)
        self.assertEqual(profile.direction_id, self.direction.id)
        self.assertEqual(profile.subjects.count(), 2)
        self.assertEqual(profile.exam_date.isoformat(), future)
        self.assertEqual(len(res.data["days"]), 7)

    def test_plan_shortens_when_exam_is_close(self):
        near = (timezone.localdate() + timedelta(days=3)).isoformat()
        res = self.client.post(
            "/api/onboarding/", self._payload(exam_date=near), format="json"
        )
        self.assertEqual(len(res.data["days"]), 3)
        plan = OnboardingPlan.objects.get()
        self.assertEqual(len(plan.days), 3)

    def test_daily_budget_scales_with_minutes_and_level(self):
        self.assertEqual(daily_question_budget(60, "beginner"), 24)
        self.assertEqual(daily_question_budget(60, "middle"), 30)
        self.assertEqual(daily_question_budget(60, "high"), 36)
        self.assertGreater(daily_question_budget(60, "high"), daily_question_budget(60, "beginner"))
        # Floor keeps even a 15-minute day worth opening a session on.
        self.assertEqual(daily_question_budget(15, "beginner"), 6)
        self.assertEqual(daily_question_budget(1, "beginner"), 5)
        for level in LEVEL_FACTORS:
            self.assertGreater(daily_question_budget(180, level), 0)

    def test_questions_are_distributed_over_days(self):
        res = self.client.post(
            "/api/onboarding/",
            self._payload(subjects=[self.math.id, self.lang.id]),
            format="json",
        )
        days = res.data["days"]
        self.assertEqual([d["day"] for d in days], [1, 2, 3, 4, 5, 6, 7])
        subject_ids = {
            item["subject_id"] for day in days for item in day["items"]
        }
        self.assertEqual(subject_ids, {self.math.id, self.lang.id})
        for day in days:
            self.assertLessEqual(day["questions"], 90)
            for item in day["items"]:
                self.assertLessEqual(item["questions"], MAX_QUESTIONS_PER_ITEM)
                self.assertGreaterEqual(item["questions"], 1)
                self.assertEqual(item["minutes"], item["questions"] * 2)

    def test_plan_serializes_subject_and_topic_briefs(self):
        self.client.post("/api/onboarding/", self._payload(), format="json")
        res = self.client.get("/api/onboarding/plan/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        first_item = res.data["days"][0]["items"][0]
        self.assertEqual(first_item["subject"]["id"], self.math.id)
        self.assertIsNotNone(first_item["subject"]["slug"])
        self.assertEqual(res.data["today"], 1)
        self.assertEqual(res.data["profile"]["daily_minutes"], 60)
        self.assertTrue(res.data["profile"]["needs_onboarding"] is False)

    def test_resubmitting_replaces_previous_plan(self):
        self.client.post("/api/onboarding/", self._payload(), format="json")
        self.client.post(
            "/api/onboarding/", self._payload(subjects=[self.lang.id]), format="json"
        )
        plan = OnboardingPlan.objects.get()
        self.assertEqual(OnboardingPlan.objects.count(), 1)
        subject_ids = {
            item["subject_id"] for day in plan.days for item in day["items"]
        }
        self.assertEqual(subject_ids, {self.lang.id})

    def test_skipped_profile_can_run_wizard_again(self):
        self.client.post("/api/onboarding/skip/")
        res = self.client.post("/api/onboarding/", self._payload(), format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        profile = OnboardingProfile.objects.get(user=self.user)
        self.assertFalse(profile.skipped)
        self.assertTrue(profile.completed)


class OnboardingWeakSubjectTests(OnboardingBaseTests):
    def _wrong_answer(self, subject, question, option_is_correct=False):
        session = PracticeSession.objects.create(
            user=self.user,
            subject=subject,
            status=PracticeSession.Status.FINISHED,
            question_count=1,
        )
        answer = PracticeAnswer.objects.create(
            session=session,
            question=question,
            selected_option=question.options.get(is_correct=option_is_correct),
            is_correct=option_is_correct,
        )
        return answer

    def test_weak_subject_gets_more_questions(self):
        weak_q = _question(self.lang, "Zaif fan savoli")
        good_q = _question(self.math, "Kuchli fan savoli")
        for _ in range(6):
            self._wrong_answer(self.lang, weak_q)
        self._wrong_answer(self.math, good_q, option_is_correct=True)

        res = self.client.post(
            "/api/onboarding/",
            self._payload(subjects=[self.math.id, self.lang.id]),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        plan = OnboardingPlan.objects.get()
        self.assertEqual(plan.weak_subject_ids, [self.lang.id])
        self.assertEqual(
            [w["id"] for w in res.data["weak_subjects"]], [self.lang.id]
        )
        per_subject = {}
        for day in plan.days:
            for item in day["items"]:
                per_subject[item["subject_id"]] = (
                    per_subject.get(item["subject_id"], 0) + item["questions"]
                )
        self.assertGreater(per_subject[self.lang.id], per_subject[self.math.id])

    def test_mastered_mistake_is_not_weak(self):
        q = _question(self.lang, "Keyin to'g'ri ishlagan savol")
        self._wrong_answer(self.lang, q)
        self._wrong_answer(self.lang, q, option_is_correct=True)
        self.client.post(
            "/api/onboarding/", self._payload(subjects=[self.lang.id]), format="json"
        )
        self.assertEqual(OnboardingPlan.objects.get().weak_subject_ids, [])

    def test_other_users_mistakes_do_not_leak(self):
        other = User.objects.create_user(username="student2", password="Passw0rd!")
        q = _question(self.lang, "Boshqa foydalanuvchi xatosi")
        session = PracticeSession.objects.create(
            user=other,
            subject=self.lang,
            status=PracticeSession.Status.FINISHED,
            question_count=1,
        )
        PracticeAnswer.objects.create(
            session=session,
            question=q,
            selected_option=q.options.get(is_correct=False),
            is_correct=False,
        )
        self.client.post(
            "/api/onboarding/", self._payload(subjects=[self.lang.id]), format="json"
        )
        self.assertEqual(OnboardingPlan.objects.get().weak_subject_ids, [])
