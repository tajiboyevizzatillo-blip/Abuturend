"""Zaif mavzular radari вЂ” hisoblash, ishonchlilik qoidasi, ro'li va tarif.

Manbalar:
* ``practice/weak_skills.py`` вЂ” agregat mantiqi va endpointlar.
* ``WEAK_SKILL_*`` sozlamalari вЂ” chegaralar ``config/settings.py`` da.
"""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Subject, Topic
from practice.models import PracticeAnswer, PracticeSession
from questions.models import Question, QuestionOption

User = get_user_model()


class WeakSkillTestBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="radar_student", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.other = User.objects.create_user(
            username="radar_other", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.math = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.lang = Subject.objects.create(name_uz="Ona tili", slug="ona-tili")
        self.functions = Topic.objects.create(
            subject=self.math, name_uz="Funksiyalar", slug="funksiyalar"
        )
        self.geometry = Topic.objects.create(
            subject=self.math, name_uz="Geometriya", slug="geometriya"
        )
        self.grammar = Topic.objects.create(
            subject=self.lang, name_uz="Grammatika", slug="grammatika"
        )
        self.client.force_login(self.user)

    def make_question(self, topic, subject=None):
        subject = subject or topic.subject
        question = Question.objects.create(
            subject=subject,
            topic=topic,
            text_uz="Savol?",
            status=Question.Status.PUBLISHED,
        )
        QuestionOption.objects.create(
            question=question, text_uz="to'g'ri", is_correct=True, sort_order=0
        )
        QuestionOption.objects.create(
            question=question, text_uz="noto'g'ri", is_correct=False, sort_order=1
        )
        return question

    def answer(self, question, is_correct, session=None):
        """One recorded answer inside a finished session."""
        session = session or self._finished_session(question.subject)
        option = question.options.filter(is_correct=is_correct).first()
        return PracticeAnswer.objects.create(
            session=session,
            question=question,
            selected_option=option,
            is_correct=is_correct,
        )

    def _finished_session(self, subject):
        session = PracticeSession.objects.create(
            user=self.user,
            subject=subject,
            status=PracticeSession.Status.FINISHED,
            question_count=1,
            finished_at=timezone.now(),
        )
        return session

    def answers_in_one_session(self, questions, correct_flags):
        """Record many answers in a SINGLE finished session.

        Two reasons over the one-session-per-answer helper: it keeps the test
        data realistic (a real session holds many questions) and it does not
        burn the free daily session limit, which the practice endpoints
        enforce.
        """
        session = self._finished_session(questions[0].subject)
        PracticeSession.objects.filter(pk=session.pk).update(
            question_count=len(questions)
        )
        for question, is_correct in zip(questions, correct_flags):
            PracticeAnswer.objects.create(
                session=session,
                question=question,
                selected_option=question.options.filter(is_correct=is_correct).first(),
                is_correct=is_correct,
            )
        return session


class RadarComputationTests(WeakSkillTestBase):
    def test_accuracy_per_topic(self):
        questions = [self.make_question(self.functions) for _ in range(6)]
        self.answers_in_one_session(questions, [index < 2 for index in range(6)])  # 2/6 = 33%

        from practice.weak_skills import topic_stats

        stats = topic_stats(self.user)
        row = next(s for s in stats if s["topic_id"] == self.functions.id)
        self.assertEqual(row["answered"], 6)
        self.assertEqual(row["correct"], 2)
        self.assertEqual(row["wrong"], 4)
        self.assertEqual(row["accuracy"], 33)
        self.assertTrue(row["enough_data"])
        self.assertTrue(row["is_weak"])

    def test_min_answers_rule_keeps_thin_topics_out(self):
        # 4 answers < WEAK_SKILL_MIN_ANSWERS (5) -> "yetarli ma'lumot yo'q".
        questions = [self.make_question(self.functions) for _ in range(4)]
        self.answers_in_one_session(questions, [False] * 4)

        from practice.weak_skills import topic_stats, weakest_topics

        row = next(s for s in topic_stats(self.user) if s["topic_id"] == self.functions.id)
        self.assertFalse(row["enough_data"])
        self.assertFalse(row["is_weak"], "kam javobli mavzu zaif deb hisoblanmasin")
        self.assertEqual(weakest_topics(self.user), [])

    def test_untouched_questions_become_other_bucket(self):
        # No topic -> the question is grouped into the virtual "Boshqa" bucket.
        questions = [self.make_question(None, subject=self.math) for _ in range(5)]
        self.answers_in_one_session(questions, [False] * 5)

        from practice.weak_skills import topic_stats

        row = next(s for s in topic_stats(self.user) if s["is_other"])
        self.assertIsNone(row["topic_id"])
        self.assertEqual(row["topic_name_uz"], "Boshqa")
        self.assertEqual(row["answered"], 5)
        self.assertTrue(row["is_weak"])

    def test_only_answered_questions_count(self):
        # Unanswered rows (no selected_option) must not distort accuracy.
        session = self._finished_session(self.math)
        question = self.make_question(self.functions)
        PracticeAnswer.objects.create(session=session, question=question)

        from practice.weak_skills import topic_stats

        self.assertEqual(topic_stats(self.user), [])

    def test_draft_questions_are_ignored(self):
        question = self.make_question(self.functions)
        question.status = Question.Status.DRAFT
        question.save()
        self.answer(question, is_correct=False)

        from practice.weak_skills import topic_stats

        self.assertEqual(topic_stats(self.user), [])

    def test_subject_radar_values(self):
        functions = [self.make_question(self.functions) for _ in range(4)]
        self.answers_in_one_session(functions, [index < 3 for index in range(4)])
        grammar = [self.make_question(self.grammar) for _ in range(5)]
        self.answers_in_one_session(grammar, [False] * 5)

        from practice.weak_skills import subject_stats

        rows = {s["subject_id"]: s for s in subject_stats(self.user)}
        self.assertEqual(rows[self.math.id]["accuracy"], 75)
        self.assertEqual(rows[self.lang.id]["accuracy"], 0)
        self.assertEqual(rows[self.math.id]["enough_data"], False)  # 4 < 5
        self.assertEqual(rows[self.lang.id]["enough_data"], True)

    @override_settings(WEAK_SKILL_THRESHOLD=51)
    def test_threshold_is_configurable(self):
        from practice.weak_skills import topic_stats

        questions = [self.make_question(self.functions) for _ in range(6)]
        self.answers_in_one_session(questions, [index < 3 for index in range(6)])  # 50%
        row = next(s for s in topic_stats(self.user) if s["topic_id"] == self.functions.id)
        self.assertEqual(row["accuracy"], 50)
        self.assertTrue(row["is_weak"], "chegara 51% bo'lganda 50% zaif hisoblanadi")

    @override_settings(WEAK_SKILL_THRESHOLD=50)
    def test_boundary_is_not_weak(self):
        from practice.weak_skills import topic_stats

        questions = [self.make_question(self.functions) for _ in range(6)]
        self.answers_in_one_session(questions, [index < 3 for index in range(6)])  # 50%
        row = next(s for s in topic_stats(self.user) if s["topic_id"] == self.functions.id)
        self.assertEqual(row["accuracy"], 50)
        self.assertFalse(row["is_weak"], "chegara bilan teng bo'lgan foiz zaif emas")

    def test_user_data_is_isolated(self):
        from practice.weak_skills import subject_stats, topic_stats

        questions = [self.make_question(self.functions) for _ in range(5)]
        self.answers_in_one_session(questions, [False] * 5)
        self.assertEqual(len(topic_stats(self.user)), 1)
        self.assertEqual(len(topic_stats(self.other)), 0)
        self.assertEqual(subject_stats(self.other), [])


class RadarApiTests(WeakSkillTestBase):
    def test_requires_authentication(self):
        self.client.logout()
        for url in (
            "/api/weak-skills/",
            "/api/weak-skills/math/",
            "/api/weak-skills/practice/",
        ):
            response = self.client.get(url)
            self.assertIn(
                response.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
                url,
            )

    def test_radar_payload(self):
        questions = [self.make_question(self.functions) for _ in range(6)]
        self.answers_in_one_session(questions, [index < 1 for index in range(6)])

        data = self.client.get("/api/weak-skills/").json()
        self.assertEqual(data["threshold"], 60)
        self.assertEqual(data["min_answers"], 5)
        self.assertFalse(data["is_premium"])
        self.assertTrue(data["has_data"])
        self.assertEqual(len(data["weak_topics"]), 1)
        self.assertEqual(data["weak_topics"][0]["accuracy"], 17)
        self.assertEqual(data["subjects"][0]["subject_id"], self.math.id)

    def test_free_tier_hides_extra_weak_topics(self):
        with override_settings(WEAK_SKILL_FREE_TOPICS=2):
            for topic in (self.functions, self.geometry, self.grammar):
                questions = [self.make_question(topic) for _ in range(5)]
                self.answers_in_one_session(questions, [False] * 5)

            data = self.client.get("/api/weak-skills/").json()
            self.assertEqual(len(data["weak_topics"]), 2)
            self.assertEqual(data["hidden_weak_topics"], 1)

    def test_subject_detail_accepts_id_and_slug(self):
        questions = [self.make_question(self.functions) for _ in range(5)]
        self.answers_in_one_session(questions, [False] * 5)

        by_slug = self.client.get("/api/weak-skills/matematika/").json()
        by_id = self.client.get(f"/api/weak-skills/{self.math.id}/").json()
        self.assertEqual(by_slug["subject"]["subject_id"], self.math.id)
        self.assertEqual(len(by_slug["topics"]), 1)
        self.assertIn(self.functions.id, by_slug["weak_topic_ids"])
        self.assertEqual(by_id["topics"][0]["topic_id"], self.functions.id)
        self.assertNotIn("history", by_slug, "bepul tarifda tarix yo'q")

    def test_unknown_subject_is_404(self):
        response = self.client.get("/api/weak-skills/yoqfan-bunday/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_is_pro_only(self):
        questions = [self.make_question(self.functions) for _ in range(5)]
        self.answers_in_one_session(questions, [False] * 5)
        self.assertNotIn("history", self.client.get("/api/weak-skills/matematika/").json())

        from premium.models import SubscriptionPlan
        from premium.services import activate_plan

        plan = SubscriptionPlan.objects.create(
            code="pro-test",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=1,
            max_sessions_per_day=None,
        )
        activate_plan(self.user, plan)

        data = self.client.get("/api/weak-skills/matematika/").json()
        self.assertIn("history", data)
        self.assertTrue(data["is_premium"])
        self.assertIn(self.functions.id, data["weak_topic_ids"])

    def test_weak_practice_requires_premium(self):
        questions = [self.make_question(self.functions) for _ in range(5)]
        self.answers_in_one_session(questions, [False] * 5)
        before = PracticeSession.objects.count()

        response = self.client.post(
            "/api/weak-skills/practice/", {"topic_ids": [self.functions.id]}
        )
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertTrue(response.json()["premium_required"])
        self.assertEqual(
            PracticeSession.objects.count(),
            before,
            "rad etilgan so\'rov sessiya yaratmasin",
        )

    def test_weak_practice_creates_session_for_premium(self):
        from premium.models import SubscriptionPlan
        from premium.services import activate_plan

        plan = SubscriptionPlan.objects.create(
            code="pro-test-2",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=1,
            max_sessions_per_day=None,
        )
        activate_plan(self.user, plan)
        questions = [self.make_question(self.functions) for _ in range(4)]

        response = self.client.post(
            "/api/weak-skills/practice/", {"topic_ids": [self.functions.id]}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session = PracticeSession.objects.get(id=response.json()["id"])
        self.assertEqual(session.question_count, len(questions))
        self.assertEqual(session.answers.count(), len(questions))
        self.assertIsNotNone(response.json()["current_question"])
        self.assertEqual(response.json()["subject"], self.math.id)

    def test_weak_practice_by_subject_uses_weak_topics(self):
        history = [self.make_question(self.functions) for _ in range(5)]
        self.answers_in_one_session(history, [False] * 5)
        question = self.make_question(self.functions)

        response = self.client.post(
            "/api/weak-skills/practice/", {"subject": self.math.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session = PracticeSession.objects.get(id=response.json()["id"])
        served = list(session.answers.values_list("question_id", flat=True))
        # Zaif mavzudagi barcha savollar beriladi (javoblaganlar ham) —
        # maqsad mavzuni mustahkamlash, xatolarni takrorlash emas.
        self.assertIn(question.id, served)
        self.assertEqual(
            set(served),
            set(self.functions.questions.values_list("id", flat=True)),
            "faqat zaif mavzudagi savollar berilishi kerak",
        )

    def test_weak_practice_validates_payload(self):
        response = self.client.post("/api/weak-skills/practice/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/weak-skills/practice/", {"subject": 99999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)