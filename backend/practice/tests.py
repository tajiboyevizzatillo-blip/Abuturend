from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Subject, Topic
from practice.models import Certificate, PracticeAnswer, PracticeSession
from practice.views import (
    DEFAULT_EXAM_MINUTES,
    LeaderboardView,
    MAX_EXAM_MINUTES,
)
from questions.models import Question, QuestionOption

User = get_user_model()


class PracticeApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student1", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.q1 = Question.objects.create(
            subject=self.subject,
            text_uz="2+2?",
            explanation_uz="4 ga teng",
            status=Question.Status.PUBLISHED,
            created_by=None,
        )
        QuestionOption.objects.create(question=self.q1, text_uz="3", is_correct=False, sort_order=0)
        QuestionOption.objects.create(question=self.q1, text_uz="4", is_correct=True, sort_order=1)
        self.q2 = Question.objects.create(
            subject=self.subject,
            text_uz="3*3?",
            explanation_uz="9 ga teng",
            status=Question.Status.PUBLISHED,
        )
        QuestionOption.objects.create(question=self.q2, text_uz="9", is_correct=True, sort_order=0)
        QuestionOption.objects.create(question=self.q2, text_uz="6", is_correct=False, sort_order=1)
        self.hidden = Question.objects.create(
            subject=self.subject, text_uz="Yashirin", status=Question.Status.DRAFT
        )
        QuestionOption.objects.create(question=self.hidden, text_uz="A", is_correct=True, sort_order=0)
        self.client.force_login(self.user)

    def _start(self, count=2):
        return self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": count, "mode": "practice"},
            format="json",
        )

    def test_start_session_returns_current_question(self):
        res = self._start()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("current_question", res.data)
        self.assertNotIn("is_correct", res.data["current_question"]["options"][0])

    def test_start_empty_pool_rejected(self):
        empty = Subject.objects.create(name_uz="Bo'sh fan", slug="bosh-fan")
        res = self.client.post(
            "/api/sessions/",
            {"subject": empty.id, "question_count": 10, "mode": "practice"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_answer_correct(self):
        session = self._start().data
        option_id = self.q1.options.get(is_correct=True).id
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": option_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_correct"])
        self.assertEqual(res.data["correct_option_id"], self.q1.options.get(is_correct=True).id)
        self.assertEqual(res.data["correct_count"], 1)

    def test_answer_wrong_records_incorrect(self):
        session = self._start().data
        option_id = self.q1.options.get(is_correct=False).id
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": option_id},
            format="json",
        )
        self.assertFalse(res.data["is_correct"])
        self.assertEqual(res.data["correct_count"], 0)

    def test_can_change_answer_before_finish(self):
        """Exam mode lets a student revisit a question and pick another option."""
        session = self._start().data
        wrong_id = self.q1.options.get(is_correct=False).id
        correct_id = self.q1.options.get(is_correct=True).id
        url = f"/api/sessions/{session['id']}/answer/"
        self.assertEqual(
            self.client.post(
                url,
                {"question_id": self.q1.id, "option_id": wrong_id},
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )
        res = self.client.post(
            url,
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_correct"])
        # Switching from wrong to right must fix *both* counters, not just add to
        # the correct one.
        self.assertEqual(res.data["correct_count"], 1)
        session_row = PracticeSession.objects.get(pk=session["id"])
        self.assertEqual(session_row.correct_answers, 1)
        self.assertEqual(session_row.incorrect_answers, 0)
        self.assertEqual(session_row.progress_index, 1)
        self.assertEqual(
            PracticeAnswer.objects.get(
                session=session_row, question=self.q1
            ).selected_option_id,
            correct_id,
        )

    def test_answer_question_without_correct_option(self):
        """A question with no correct option must not 500 the student."""
        broken = Question.objects.create(
            subject=self.subject,
            text_uz="Javobsiz savol",
            status=Question.Status.PUBLISHED,
        )
        QuestionOption.objects.create(
            question=broken, text_uz="A", is_correct=False, sort_order=0
        )
        QuestionOption.objects.create(
            question=broken, text_uz="B", is_correct=False, sort_order=1
        )
        session = PracticeSession.objects.create(
            user=self.user,
            subject=self.subject,
            question_count=1,
        )
        PracticeAnswer.objects.create(session=session, question=broken)
        res = self.client.post(
            f"/api/sessions/{session.id}/answer/",
            {"question_id": broken.id, "option_id": broken.options.first().id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_correct"])
        self.assertIsNone(res.data["correct_option_id"])

    def _manual_session(self, questions, mode="practice"):
        session = PracticeSession.objects.create(
            user=self.user,
            subject=self.subject,
            mode=mode,
            question_count=len(questions),
        )
        session.answers.bulk_create(
            [PracticeAnswer(session=session, question=q) for q in questions]
        )
        return session

    def test_current_ignores_answers_given_in_another_session(self):
        """Answering a question once must not hide it from the student's other
        session — the same question can legitimately sit in several of them."""
        answered_session = self._manual_session([self.q1])
        other_session = self._manual_session([self.q1, self.q2])
        self.client.post(
            f"/api/sessions/{answered_session.id}/answer/",
            {
                "question_id": self.q1.id,
                "option_id": self.q1.options.get(is_correct=True).id,
            },
            format="json",
        )
        res = self.client.get(f"/api/sessions/{other_session.id}/current/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["question"]["id"], self.q1.id)
        self.assertEqual(res.data["unanswered_count"], 2)

    def test_start_returns_first_unanswered_question(self):
        partial = self._manual_session([self.q1, self.q2])
        PracticeAnswer.objects.filter(session=partial, question=self.q1).update(
            selected_option=self.q1.options.get(is_correct=True).id, is_correct=True
        )
        res = self.client.get(f"/api/sessions/{partial.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn("current_question", res.data)

    def test_finish_reports_score(self):
        session = self._start().data
        correct_id = self.q1.options.get(is_correct=True).id
        wrong_id = self.q2.options.get(is_correct=False).id
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q2.id, "option_id": wrong_id},
            format="json",
        )
        res = self.client.post(f"/api/sessions/{session['id']}/finish/", format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["correct_answers"], 1)
        self.assertEqual(res.data["incorrect_answers"], 1)
        self.assertEqual(res.data["score_percent"], 50)
        self.assertEqual(len(res.data["questions"]), 2)
        self.assertIn("is_correct", res.data["questions"][0]["question"]["options"][0])

    def test_current_after_some_answers(self):
        session = self._start().data
        option_id = self.q1.options.get(is_correct=True).id
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": option_id},
            format="json",
        )
        res = self.client.get(f"/api/sessions/{session['id']}/current/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["question"]["id"], self.q2.id)
        self.assertEqual(res.data["unanswered_count"], 1)

    def test_other_user_cannot_access(self):
        other = User.objects.create_user(
            username="student2", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.client.force_login(other)
        res = self.client.get(f"/api/sessions/99999/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_sessions_returns_summaries(self):
        self._start()
        res = self.client.get("/api/sessions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        row = res.data["results"][0]
        self.assertEqual(row["mode"], "practice")
        self.assertEqual(row["subject"]["name_uz"], "Matematika")
        self.assertEqual(row["score_percent"], 0)
        self.assertEqual(row["unanswered"], 2)

    def test_stats_summary_aggregates(self):
        session = self._start().data
        correct_id = self.q1.options.get(is_correct=True).id
        wrong_id = self.q2.options.get(is_correct=False).id
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q2.id, "option_id": wrong_id},
            format="json",
        )
        self.client.post(f"/api/sessions/{session['id']}/finish/", format="json")

        res = self.client.get("/api/stats/summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_finished"], 1)
        self.assertEqual(res.data["total_answered"], 2)
        self.assertEqual(res.data["accuracy"], 50)
        self.assertEqual(res.data["current_score"], 50)
        self.assertEqual(res.data["streak"], 1)
        self.assertEqual(len(res.data["weekly_activity"]), 7)
        self.assertEqual(res.data["weekly_activity"][-1]["answered"], 2)
        self.assertEqual(res.data["recent_sessions"][0]["score_percent"], 50)

        subj = next(
            s for s in res.data["subject_breakdown"] if s["subject_id"] == self.subject.id
        )
        self.assertEqual(subj["accuracy"], 50)
        self.assertEqual(subj["sessions"], 1)

        with self.subTest("weak_topics"):
            topic = Topic.objects.create(
                subject=self.subject, name_uz="Hisob-kitob", slug="hisob-kitob"
            )
            self.q2.topic = topic
            self.q2.save(update_fields=["topic"])
            cm = self.client
            res2 = self.client.get("/api/stats/summary/")
            self.assertGreaterEqual(len(res2.data["weak_topics"]), 1)

    def test_questions_list_hides_correct_answers(self):
        session = self._start().data
        res = self.client.get(f"/api/sessions/{session['id']}/questions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["questions"]), 2)
        for q in res.data["questions"]:
            for option in q["options"]:
                self.assertNotIn("is_correct", option)

    def test_report_hidden_until_finished(self):
        session = self._start().data
        correct_id = self.q1.options.get(is_correct=True).id
        self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        # Mid-session the report would leak the answer key for unanswered
        # questions, so it stays closed until the session is finished.
        blocked = self.client.get(f"/api/sessions/{session['id']}/report/")
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)

        finish = self.client.post(f"/api/sessions/{session['id']}/finish/", format="json")
        self.assertEqual(finish.status_code, status.HTTP_200_OK)
        res = self.client.get(f"/api/sessions/{session['id']}/report/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "finished")
        self.assertEqual(res.data["correct_answers"], 1)
        self.assertEqual(len(res.data["questions"]), 2)
        answered = next(
            q for q in res.data["questions"] if q["question"]["id"] == self.q1.id
        )
        self.assertEqual(answered["is_correct"], True)
        self.assertEqual(answered["selected_option_id"], correct_id)
        self.assertIn("explanation_uz", answered["question"])

    def test_exam_answer_never_leaks_correctness(self):
        session = self.client.post(
            "/api/sessions/",
            {
                "subject": self.subject.id,
                "question_count": 2,
                "mode": "exam",
            },
            format="json",
        ).data
        correct_id = self.q1.options.get(is_correct=True).id
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn("is_correct", res.data)
        self.assertNotIn("correct_option_id", res.data)
        self.assertNotIn("explanation_uz", res.data)
        # The running correct-count itself is an answer oracle when a student
        # can change their choice and diff the numbers, so it must not exist.
        self.assertNotIn("correct_count", res.data)
        self.assertEqual(res.data["answered_count"], 1)
        self.assertEqual(res.data["total_count"], 2)

    def test_exam_running_score_hidden_from_session_payloads(self):
        create = self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": 2, "mode": "exam"},
            format="json",
        )
        self.assertIsNone(create.data["correct_answers"])
        self.assertIsNone(create.data["incorrect_answers"])
        self.assertIsNotNone(create.data["deadline_at"])

        correct_id = self.q1.options.get(is_correct=True).id
        self.client.post(
            f"/api/sessions/{create.data['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        detail = self.client.get(f"/api/sessions/{create.data['id']}/")
        self.assertIsNone(detail.data["correct_answers"])

        listed = self.client.get("/api/sessions/")
        row = next(r for r in listed.data["results"] if r["id"] == create.data["id"])
        self.assertIsNone(row["correct_answers"])
        self.assertIsNone(row["score_percent"])

        # Once finished the score becomes visible again.
        finish = self.client.post(
            f"/api/sessions/{create.data['id']}/finish/", format="json"
        )
        self.assertEqual(finish.data["score_percent"], 50)
        listed = self.client.get("/api/sessions/")
        row = next(r for r in listed.data["results"] if r["id"] == create.data["id"])
        self.assertEqual(row["score_percent"], 50)

    def test_exam_answers_rejected_after_deadline(self):
        session = self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": 2, "mode": "exam"},
            format="json",
        ).data
        PracticeSession.objects.filter(pk=session["id"]).update(
            deadline_at=timezone.now() - timedelta(seconds=1)
        )
        correct_id = self.q1.options.get(is_correct=True).id
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": self.q1.id, "option_id": correct_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(res.data["time_expired"])
        # Finishing after the deadline still works and scores honestly.
        finish = self.client.post(f"/api/sessions/{session['id']}/finish/", format="json")
        self.assertEqual(finish.status_code, status.HTTP_200_OK)
        self.assertEqual(finish.data["correct_answers"], 0)

    def test_exam_duration_is_clamped_server_side(self):
        """A client cannot buy itself a longer exam by asking for one."""
        res = self.client.post(
            "/api/sessions/",
            {
                "subject": self.subject.id,
                "question_count": 2,
                "mode": "exam",
                "duration_minutes": 240,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        session = PracticeSession.objects.get(pk=res.data["id"])
        self.assertEqual(session.duration_minutes, MAX_EXAM_MINUTES)
        remaining = session.deadline_at - timezone.now()
        self.assertLess(remaining, timedelta(minutes=MAX_EXAM_MINUTES + 1))

    def test_exam_without_duration_uses_the_default(self):
        res = self.client.post(
            "/api/sessions/",
            {"subject": self.subject.id, "question_count": 2, "mode": "exam"},
            format="json",
        )
        session = PracticeSession.objects.get(pk=res.data["id"])
        self.assertEqual(session.duration_minutes, DEFAULT_EXAM_MINUTES)

    def test_practice_session_has_no_deadline(self):
        res = self.client.post(
            "/api/sessions/",
            {
                "subject": self.subject.id,
                "question_count": 2,
                "mode": "practice",
                "duration_minutes": 240,
            },
            format="json",
        )
        session = PracticeSession.objects.get(pk=res.data["id"])
        self.assertIsNone(session.deadline_at)

    def test_topic_from_another_subject_rejected(self):
        other_subject = Subject.objects.create(
            name_uz="Fizika", slug="fizika", code="PH"
        )
        foreign_topic = Topic.objects.create(
            subject=other_subject, name_uz="Mashq", slug="mashq"
        )
        res = self.client.post(
            "/api/sessions/",
            {
                "subject": self.subject.id,
                "topic": foreign_topic.id,
                "question_count": 2,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exam_report_blocked_until_finished(self):
        session = self.client.post(
            "/api/sessions/",
            {
                "subject": self.subject.id,
                "question_count": 2,
                "mode": "exam",
            },
            format="json",
        ).data
        res = self.client.get(f"/api/sessions/{session['id']}/report/")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        finish = self.client.post(f"/api/sessions/{session['id']}/finish/", format="json")
        self.assertEqual(finish.status_code, status.HTTP_200_OK)
        after = self.client.get(f"/api/sessions/{session['id']}/report/")
        self.assertEqual(after.status_code, status.HTTP_200_OK)

    def test_answer_for_foreign_question_rejected(self):
        session = self._start().data
        foreign = Question.objects.create(
            subject=self.subject,
            text_uz="Boshqa sessiya savoli",
            status=Question.Status.PUBLISHED,
        )
        QuestionOption.objects.create(question=foreign, text_uz="A", is_correct=True, sort_order=0)
        res = self.client.post(
            f"/api/sessions/{session['id']}/answer/",
            {"question_id": foreign.id, "option_id": foreign.options.first().id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stats_requires_auth(self):
        fresh = self.client.__class__()
        self.assertEqual(
            fresh.get("/api/stats/summary/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def _finished_session(self, user, correct, incorrect=0):
        return PracticeSession.objects.create(
            user=user,
            subject=self.subject,
            status=PracticeSession.Status.FINISHED,
            question_count=correct + incorrect,
            correct_answers=correct,
            incorrect_answers=incorrect,
        )

    def test_leaderboard_public_and_sorted(self):
        top = User.objects.create_user(
            username="top_user",
            first_name="Ali",
            password="Passw0rd!",
            role=User.Role.STUDENT,
        )
        mid = User.objects.create_user(
            username="mid_user",
            password="Passw0rd!",
            role=User.Role.STUDENT,
        )
        self._finished_session(top, correct=8, incorrect=2)
        self._finished_session(top, correct=2)
        self._finished_session(mid, correct=5, incorrect=5)
        staff = User.objects.create_superuser(
            username="staff_user", password="Passw0rd!", email="staff@test.com"
        )
        self._finished_session(staff, correct=100)

        res = self.client.__class__().get("/api/leaderboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(res.data[0]["rank"], 1)
        self.assertEqual(res.data[0]["display_name"], "Ali")
        self.assertEqual(res.data[0]["correct_answers"], 10)
        self.assertEqual(res.data[0]["finished_sessions"], 2)
        self.assertEqual(res.data[0]["total_answered"], 12)
        self.assertEqual(res.data[0]["accuracy_percent"], 83)
        self.assertEqual(res.data[1]["rank"], 2)
        # Raw usernames stay private on the public leaderboard.
        self.assertEqual(res.data[1]["display_name"], "mi***")
        self.assertGreater(
            res.data[0]["correct_answers"], res.data[1]["correct_answers"]
        )
        self.assertFalse(any(row["display_name"] == "staff_user" for row in res.data))

    def test_leaderboard_excludes_users_without_finished_sessions(self):
        User.objects.create_user(
            username="noob", password="Passw0rd!", role=User.Role.STUDENT
        )
        res = self.client.__class__().get("/api/leaderboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_leaderboard_declares_a_throttle_scope(self):
        """The public leaderboard runs whole-table aggregates, so it must rate limit.

        Asserted on configuration rather than by exhausting the bucket: DRF
        throttle history lives in the (process-wide) cache and the test runner
        reuses one process, so actually tripping the limit would leak into every
        later leaderboard test in the suite.
        """
        self.assertEqual(LeaderboardView.throttle_scope, "public_read")
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertIn("public_read", rates)
        self.assertEqual(
            LeaderboardView.permission_classes[0].__name__, "AllowAny"
        )

    def test_leaderboard_limit_param(self):
        for i in range(3):
            user = User.objects.create_user(
                username=f"racer{i}", password="Passw0rd!", role=User.Role.STUDENT
            )
            self._finished_session(user, correct=10 - i, incorrect=i)
        guest = self.client.__class__()
        # Default stays 10 for the landing widget.
        self.assertEqual(len(guest.get("/api/leaderboard/").data), 3)
        res = guest.get("/api/leaderboard/?limit=2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        self.assertEqual(res.data[0]["rank"], 1)
        # Garbage and out-of-range values fall back to a safe window.
        self.assertEqual(len(guest.get("/api/leaderboard/?limit=abc").data), 3)
        self.assertEqual(len(guest.get("/api/leaderboard/?limit=0").data), 3)


class UnifiedExamTests(APITestCase):
    """Umumiy imtihon: a subject-less exam session sampled across subjects."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="uni_student", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.s1 = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.s2 = Subject.objects.create(name_uz="Fizika", slug="fizika")
        for i, subject in enumerate([self.s1, self.s1, self.s2, self.s2]):
            q = Question.objects.create(
                subject=subject, text_uz=f"Savol {i}", status=Question.Status.PUBLISHED
            )
            QuestionOption.objects.create(
                question=q, text_uz="To'g'ri", is_correct=True, sort_order=0
            )
            QuestionOption.objects.create(
                question=q, text_uz="Noto'g'ri", is_correct=False, sort_order=1
            )
        draft = Question.objects.create(
            subject=self.s2, text_uz="Qoralama", status=Question.Status.DRAFT
        )
        QuestionOption.objects.create(
            question=draft, text_uz="A", is_correct=True, sort_order=0
        )
        self.client.force_login(self.user)

    def test_unified_exam_samples_across_subjects(self):
        res = self.client.post(
            "/api/sessions/",
            {"mode": "exam", "question_count": 4, "duration_minutes": 30},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(res.data["subject"])
        self.assertTrue(res.data["unified"])
        self.assertIsNotNone(res.data["deadline_at"])

        qs = self.client.get(f"/api/sessions/{res.data['id']}/questions/")
        self.assertEqual(qs.status_code, status.HTTP_200_OK)
        qids = [q["id"] for q in qs.data["questions"]]
        subject_ids = set(
            Question.objects.filter(id__in=qids).values_list("subject_id", flat=True)
        )
        self.assertEqual(subject_ids, {self.s1.id, self.s2.id})
        self.assertEqual(len(qs.data["questions"]), 4)
        # Draft questions never reach the paper.
        texts = {q["text_uz"] for q in qs.data["questions"]}
        self.assertNotIn("Qoralama", texts)

    def test_unified_requires_exam_mode(self):
        res = self.client.post(
            "/api/sessions/", {"mode": "practice", "question_count": 2}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("subject", res.data)

    def test_topic_without_subject_rejected(self):
        topic = Topic.objects.create(subject=self.s1, name_uz="Mavzu")
        res = self.client.post(
            "/api/sessions/",
            {"mode": "exam", "topic": topic.id, "question_count": 2},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("topic", res.data)


class CertificateTests(APITestCase):
    """Server-issued certificates: style choice, threshold, public verify."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="cert_student",
            first_name="Ali",
            last_name="Valiyev",
            password="Passw0rd!",
            role=User.Role.STUDENT,
        )
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.client.force_login(self.user)

    def _finished_unified(self, correct, total, user=None):
        session = PracticeSession.objects.create(
            user=user or self.user,
            mode=PracticeSession.Mode.EXAM,
            subject=None,
            status=PracticeSession.Status.FINISHED,
            question_count=total,
            correct_answers=correct,
            incorrect_answers=total - correct,
            finished_at=timezone.now(),
        )
        return session

    def _issue(self, session, style="international"):
        return self.client.post(
            "/api/certificates/",
            {"session": session.id, "style": style},
            format="json",
        )

    def test_issue_international_certificate(self):
        session = self._finished_unified(correct=9, total=10)
        res = self._issue(session)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertRegex(res.data["serial"], r"^ABT-\d{4}-[A-Z0-9]{6}$")
        self.assertEqual(res.data["score_percent"], 90)
        self.assertEqual(res.data["grade"], "C1")  # 90%+ band
        self.assertTrue(res.data["passed"])
        self.assertEqual(res.data["full_name"], "Ali Valiyev")
        self.assertEqual(res.data["style"], "international")

    def test_certificate_idempotent_per_style(self):
        session = self._finished_unified(correct=8, total=10)
        first = self._issue(session)
        second = self._issue(session)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(first.data["serial"], second.data["serial"])

    def test_local_style_uses_sixty_percent_threshold(self):
        failed = self._finished_unified(correct=5, total=10)
        res = self._issue(failed, style="local")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data["passed"])
        self.assertEqual(res.data["score_percent"], 50)
        self.assertEqual(res.data["grade"], "A2")

        passed = self._finished_unified(correct=6, total=10)
        res = self._issue(passed, style="local")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["passed"])
        self.assertEqual(res.data["grade"], "B1")

        # Both styles of the same exam coexist as separate documents.
        res = self._issue(passed, style="international")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_certificate_requires_finished_unified_exam(self):
        running = PracticeSession.objects.create(
            user=self.user,
            mode=PracticeSession.Mode.EXAM,
            subject=None,
            status=PracticeSession.Status.IN_PROGRESS,
            question_count=2,
        )
        res = self._issue(running)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        finished_subject = PracticeSession.objects.create(
            user=self.user,
            mode=PracticeSession.Mode.EXAM,
            subject=self.subject,
            status=PracticeSession.Status.FINISHED,
            question_count=2,
            correct_answers=2,
        )
        res = self._issue(finished_subject)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_certify_other_users_session(self):
        other = User.objects.create_user(
            username="other_student", password="Passw0rd!", role=User.Role.STUDENT
        )
        session = self._finished_unified(correct=10, total=10, user=other)
        res = self._issue(session)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Certificate.objects.filter(session=session).exists())

    def test_list_returns_only_own_certificates(self):
        mine = self._finished_unified(correct=7, total=10)
        self._issue(mine)
        other = User.objects.create_user(
            username="other_holder", password="Passw0rd!", role=User.Role.STUDENT
        )
        other_session = self._finished_unified(correct=3, total=10, user=other)
        Certificate.objects.create(
            session=other_session,
            user=other,
            serial="ABT-2026-ZZZZZZ",
            style=Certificate.Style.LOCAL,
            full_name="Boshqa O'quvchi",
            score_percent=30,
            correct_answers=3,
            question_count=10,
            grade="A2",
            passed=False,
        )
        res = self.client.get("/api/certificates/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertNotEqual(res.data[0]["serial"], "ABT-2026-ZZZZZZ")

    def test_public_verify_by_serial(self):
        session = self._finished_unified(correct=8, total=10)
        issued = self._issue(session).data

        fresh = self.client.__class__()  # no auth on purpose
        res = fresh.get(f"/api/certificates/{issued['serial']}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["serial"], issued["serial"])
        self.assertEqual(res.data["score_percent"], 80)
        self.assertEqual(res.data["grade"], "B2")

        missing = fresh.get("/api/certificates/ABT-2026-NOTHERE/")
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

        # The list endpoint stays private.
        self.assertEqual(
            fresh.get("/api/certificates/").status_code, status.HTTP_403_FORBIDDEN
        )

    def test_unified_finished_session_does_not_break_stats(self):
        self._finished_unified(correct=4, total=5)
        res = self.client.get("/api/stats/summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_finished"], 1)
        self.assertEqual(res.data["total_questions"], 5)
        # Unified results never appear as a per-subject bucket.
        self.assertEqual(res.data["subject_breakdown"], [])

class MistakesTests(APITestCase):
    """Xatolar daftari: question_ids sessions + GET /api/stats/mistakes/."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="mistaker", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.subject = Subject.objects.create(name_uz="Fizika", slug="fizika")
        self.q1 = self._question("Tezlik birliklari?")
        self.q2 = self._question("Kuch formulasi?")
        self.hidden = Question.objects.create(
            subject=self.subject, text_uz="Yashirin savol", status=Question.Status.DRAFT
        )
        QuestionOption.objects.create(
            question=self.hidden, text_uz="A", is_correct=True, sort_order=0
        )
        self.client.force_login(self.user)

    def _question(self, text):
        q = Question.objects.create(
            subject=self.subject,
            text_uz=text,
            explanation_uz="Tushuntirish",
            status=Question.Status.PUBLISHED,
        )
        QuestionOption.objects.create(question=q, text_uz="To'g'ri", is_correct=True, sort_order=0)
        QuestionOption.objects.create(question=q, text_uz="Xato", is_correct=False, sort_order=1)
        return q

    def _answered(self, items, mode="practice", status=None, finished_at=None):
        session = PracticeSession.objects.create(
            user=self.user,
            subject=self.subject,
            mode=mode,
            question_count=len(items),
            status=status or PracticeSession.Status.FINISHED,
            finished_at=(
                finished_at if finished_at is not None else timezone.now()
            ),
        )
        for q, ok in items:
            PracticeAnswer.objects.create(
                session=session, question=q, is_correct=ok
            )
        return session

    def test_start_with_question_ids_uses_exact_pool_in_order(self):
        res = self.client.post(
            "/api/sessions/",
            {"mode": "practice", "question_ids": [self.q2.id, self.q1.id]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["question_count"], 2)
        self.assertIsNone(res.data["subject"])
        self.assertEqual(res.data["mode"], "practice")
        # A mistakes session is not a unified exam, even without a subject.
        self.assertFalse(res.data["unified"])
        self.assertEqual(res.data["current_question"]["id"], self.q2.id)
        session = PracticeSession.objects.get(pk=res.data["id"])
        self.assertEqual(
            [a.question_id for a in session.answers.order_by("id")],
            [self.q2.id, self.q1.id],
        )

    def test_start_with_question_ids_rejects_unpublished(self):
        res = self.client.post(
            "/api/sessions/",
            {"mode": "practice", "question_ids": [self.q1.id, self.hidden.id]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_with_question_ids_rejects_duplicates(self):
        res = self.client.post(
            "/api/sessions/",
            {"mode": "practice", "question_ids": [self.q1.id, self.q1.id]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_question_ids_require_practice_mode_without_subject(self):
        exam = self.client.post(
            "/api/sessions/",
            {"mode": "exam", "question_ids": [self.q1.id]},
            format="json",
        )
        self.assertEqual(exam.status_code, status.HTTP_400_BAD_REQUEST)
        with_subject = self.client.post(
            "/api/sessions/",
            {"mode": "practice", "subject": self.subject.id, "question_ids": [self.q1.id]},
            format="json",
        )
        self.assertEqual(with_subject.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mistakes_lists_wrong_answers_with_counts(self):
        self._answered([(self.q1, False), (self.q2, True)])
        self._answered([(self.q1, False)])
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total"], 1)
        self.assertEqual(len(res.data["items"]), 1)
        item = res.data["items"][0]
        self.assertEqual(item["question_id"], self.q1.id)
        self.assertEqual(item["wrong"], 2)
        self.assertEqual(item["subject_name_uz"], "Fizika")
        self.assertFalse(item["is_mastered"])
        self.assertIsNotNone(item["last_wrong_at"])

    def test_mistakes_sorted_by_wrong_count(self):
        self._answered([(self.q2, False)])
        self._answered([(self.q1, False)])
        self._answered([(self.q1, False)])
        res = self.client.get("/api/stats/mistakes/")
        ids = [i["question_id"] for i in res.data["items"]]
        self.assertEqual(ids, [self.q1.id, self.q2.id])

    def test_mastered_flips_when_later_answer_is_correct(self):
        self._answered([(self.q1, False)])
        self._answered([(self.q1, True)])
        res = self.client.get("/api/stats/mistakes/")
        item = res.data["items"][0]
        self.assertTrue(item["is_mastered"])
        # Still part of the notebook total (it was answered wrongly at least once).
        self.assertEqual(res.data["total"], 1)

    def test_mistakes_ignores_abandoned_sessions(self):
        """Answers from an unfinished attempt must not enter the notebook.

        An abandoned attempt (closed tab, crash) can never be finished, so
        counting its wrong answers inflated `total`/`wrong` permanently and
        contradicted the view's own docstring.
        """
        self._answered(
            [(self.q1, False)],
            status=PracticeSession.Status.IN_PROGRESS,
            finished_at=None,
        )
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.data["total"], 0)
        self.assertEqual(res.data["items"], [])

    def test_mistakes_mixes_finished_and_abandoned_correctly(self):
        self._answered([(self.q1, False)])
        self._answered(
            [(self.q2, False)],
            status=PracticeSession.Status.IN_PROGRESS,
            finished_at=None,
        )
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.data["total"], 1)
        self.assertEqual(res.data["items"][0]["question_id"], self.q1.id)

    def test_mistakes_excludes_question_unpublished_later(self):
        self._answered([(self.q1, False)])
        self.q1.status = Question.Status.DRAFT
        self.q1.save(update_fields=["status"])
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.data["total"], 0)
        self.assertEqual(res.data["items"], [])

    def test_mistakes_empty_notebook(self):
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"total": 0, "count": 0, "items": []})

    def test_mistakes_requires_login(self):
        self.client.logout()
        res = self.client.get("/api/stats/mistakes/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
