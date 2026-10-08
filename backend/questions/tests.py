from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Subject
from questions.models import Question, QuestionOption

User = get_user_model()


class QuestionApiTests(APITestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.teacher = User.objects.create_user(
            username="teacher1", password="Passw0rd!", role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(
            username="student1", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.q = Question.objects.create(
            subject=self.subject,
            text_uz="2+2 nechaga teng?",
            difficulty=Question.Difficulty.EASY,
            status=Question.Status.PUBLISHED,
            created_by=self.teacher,
        )
        QuestionOption.objects.create(question=self.q, text_uz="3", is_correct=False, sort_order=1)
        QuestionOption.objects.create(question=self.q, text_uz="4", is_correct=True, sort_order=2)
        self.draft = Question.objects.create(
            subject=self.subject,
            text_uz="Qoralama savol",
            status=Question.Status.DRAFT,
            created_by=self.teacher,
        )
        QuestionOption.objects.create(question=self.draft, text_uz="A", is_correct=True, sort_order=1)
        QuestionOption.objects.create(question=self.draft, text_uz="B", is_correct=False, sort_order=2)

    def _auth(self, user):
        self.client.force_login(user)

    def test_student_sees_only_published_without_correct(self):
        self._auth(self.student)
        res = self.client.get("/api/questions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [q["id"] for q in res.data["results"]]
        self.assertIn(self.q.id, ids)
        self.assertNotIn(self.draft.id, ids)
        first = res.data["results"][0]
        self.assertNotIn("is_correct", first["options"][0])
        self.assertNotIn("explanation_uz", first)

    def test_student_cannot_create(self):
        self._auth(self.student)
        res = self.client.post(
            "/api/questions/",
            {"subject": self.subject.id, "text_uz": "?",
             "options": [{"text_uz": "1", "is_correct": True}]},
            format="json",
        )
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED))

    def test_teacher_can_create_full(self):
        self._auth(self.teacher)
        res = self.client.post(
            "/api/questions/",
            {
                "subject": self.subject.id,
                "topic": None,
                "text_uz": "12*12?",
                "text_ru": "",
                "text_en": "",
                "question_type": "single",
                "difficulty": 2,
                "explanation_uz": "144",
                "source_type": "custom",
                "status": "draft",
                "options": [
                    {"text_uz": "140", "is_correct": False, "sort_order": 1},
                    {"text_uz": "144", "is_correct": True, "sort_order": 2},
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        q = Question.objects.get(pk=res.data["id"])
        self.assertEqual(q.options.filter(is_correct=True).count(), 1)
        self.assertEqual(q.created_by, self.teacher)

    def test_create_requires_correct_option(self):
        self._auth(self.teacher)
        res = self.client.post(
            "/api/questions/",
            {"subject": self.subject.id, "text_uz": "?",
             "options": [{"text_uz": "1", "is_correct": False}]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_single_requires_one_correct(self):
        self._auth(self.teacher)
        res = self.client.post(
            "/api/questions/",
            {"subject": self.subject.id, "text_uz": "?",
             "options": [
                 {"text_uz": "1", "is_correct": True},
                 {"text_uz": "2", "is_correct": True},
             ]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_can_update_status(self):
        self._auth(self.teacher)
        res = self.client.patch(
            f"/api/questions/{self.draft.id}/", {"status": "published"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Question.Status.PUBLISHED)

    def test_anonymous_denied(self):
        res = self.client.get("/api/questions/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ---- object-level authorization -------------------------------------

    def test_teacher_cannot_edit_another_teachers_draft(self):
        """A plain teacher is confined to the questions they authored."""
        other = User.objects.create_user(
            username="teacher2", password="Passw0rd!", role=User.Role.TEACHER
        )
        foreign = Question.objects.create(
            subject=self.subject,
            text_uz="Boshqa o'qituvchi qoralamasi",
            status=Question.Status.DRAFT,
            created_by=other,
        )
        self._auth(self.teacher)
        res = self.client.patch(
            f"/api/questions/{foreign.id}/", {"text_uz": "O'girlash"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        foreign.refresh_from_db()
        self.assertEqual(foreign.text_uz, "Boshqa o'qituvchi qoralamasi")

    def test_teacher_cannot_delete_another_teachers_question(self):
        other = User.objects.create_user(
            username="teacher2", password="Passw0rd!", role=User.Role.TEACHER
        )
        foreign = Question.objects.create(
            subject=self.subject,
            text_uz="Boshqa savol",
            status=Question.Status.PUBLISHED,
            created_by=other,
        )
        self._auth(self.teacher)
        res = self.client.delete(f"/api/questions/{foreign.id}/")
        # Denied either way: the queryset hides another teacher's draft, and a
        # published row is visible but rejected by the object permission (403).
        self.assertIn(
            res.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        self.assertTrue(Question.objects.filter(pk=foreign.pk).exists())

    def test_teacher_does_not_see_other_teachers_drafts_in_the_list(self):
        other = User.objects.create_user(
            username="teacher2", password="Passw0rd!", role=User.Role.TEACHER
        )
        foreign = Question.objects.create(
            subject=self.subject,
            text_uz="Yashirin qoralama",
            status=Question.Status.DRAFT,
            created_by=other,
        )
        self._auth(self.teacher)
        ids = [q["id"] for q in self.client.get("/api/questions/").data["results"]]
        self.assertNotIn(foreign.id, ids)

    def test_admin_role_moderates_any_question(self):
        admin = User.objects.create_user(
            username="board", password="Passw0rd!", role=User.Role.ADMIN
        )
        self._auth(admin)
        res = self.client.patch(
            f"/api/questions/{self.draft.id}/", {"status": "archived"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Question.Status.ARCHIVED)

    # ---- trust flags are not client-writable ----------------------------

    def test_teacher_cannot_set_is_verified_or_is_official(self):
        """Verification is a review decision, not something a client asserts."""
        self._auth(self.teacher)
        res = self.client.post(
            "/api/questions/",
            {
                "subject": self.subject.id,
                "text_uz": "Qo'lda qo'yilgan 'rasmiy' savol",
                "is_verified": True,
                "is_official": True,
                "options": [
                    {"text_uz": "ha", "is_correct": True},
                    {"text_uz": "yo'q", "is_correct": False},
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created = Question.objects.get(pk=res.data["id"])
        self.assertFalse(created.is_verified)
        self.assertFalse(created.is_official)

    def test_teacher_cannot_patch_is_verified(self):
        self._auth(self.teacher)
        res = self.client.patch(
            f"/api/questions/{self.q.id}/", {"is_verified": True}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.q.refresh_from_db()
        self.assertFalse(self.q.is_verified)

    def test_trust_flags_are_not_writable_through_the_api(self):
        """Verification is set in the Django admin, never over the API.

        The flags are read-only for every role, admin included: a review
        decision that can arrive from an HTTP request is not a review decision.
        Staff set them through /admin/, where the action is attributed and
        auditable.
        """
        admin = User.objects.create_user(
            username="board", password="Passw0rd!", role=User.Role.ADMIN
        )
        self._auth(admin)
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            {"is_verified": True, "is_official": True},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.q.refresh_from_db()
        self.assertFalse(self.q.is_verified)
        self.assertFalse(self.q.is_official)
        # Both flags are still reported, so the UI can display review state.
        self.assertIn("is_verified", res.data)
        self.assertIn("is_official", res.data)

    def test_ordering_defaults_to_newest_first(self):
        later = Question.objects.create(
            subject=self.subject,
            text_uz="Keyingi savol",
            status=Question.Status.PUBLISHED,
            created_by=self.teacher,
        )
        QuestionOption.objects.create(question=later, text_uz="A", is_correct=True, sort_order=1)
        QuestionOption.objects.create(question=later, text_uz="B", is_correct=False, sort_order=2)
        self._auth(self.student)
        res = self.client.get("/api/questions/")
        ids = [q["id"] for q in res.data["results"]]
        self.assertEqual(ids[:2], [later.id, self.q.id])

    def test_ordering_param_reversed(self):
        self._auth(self.student)
        res = self.client.get("/api/questions/", {"ordering": "id"})
        ids = [q["id"] for q in res.data["results"]]
        self.assertEqual(ids, [self.q.id])


class QuestionOptionSyncTests(APITestCase):
    """Options carry UNIQUE(question, sort_order); the sync must never collide.

    Reordering, inserting in the middle and removing from the middle all rewrite
    sort_order in place. Writing the final positions directly makes two rows
    briefly share a slot, which used to surface as an unhandled IntegrityError
    (HTTP 500) from the teacher UI.
    """

    def setUp(self):
        self.subject = Subject.objects.create(name_uz="Matematika", slug="matematika")
        self.teacher = User.objects.create_user(
            username="teacher1", password="Passw0rd!", role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(
            username="student1", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.q = Question.objects.create(
            subject=self.subject,
            text_uz="2+2?",
            status=Question.Status.PUBLISHED,
            created_by=self.teacher,
        )
        self.a = QuestionOption.objects.create(
            question=self.q, text_uz="A", is_correct=True, sort_order=0
        )
        self.b = QuestionOption.objects.create(
            question=self.q, text_uz="B", is_correct=False, sort_order=1
        )
        self.c = QuestionOption.objects.create(
            question=self.q, text_uz="C", is_correct=False, sort_order=2
        )
        self.client.force_login(self.teacher)

    def _options_payload(self, *options):
        return {
            "options": [
                {"id": o.id, "text_uz": o.text_uz, "is_correct": o.is_correct}
                for o in options
            ]
        }

    def _order(self):
        return [
            (o.id, o.text_uz, o.sort_order)
            for o in self.q.options.order_by("sort_order", "id")
        ]

    def test_reorder_options(self):
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            self._options_payload(self.b, self.a, self.c),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._order(), [(self.b.id, "B", 0), (self.a.id, "A", 1), (self.c.id, "C", 2)]
        )

    def test_reverse_reorder_options(self):
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            self._options_payload(self.c, self.b, self.a),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._order(), [(self.c.id, "C", 0), (self.b.id, "B", 1), (self.a.id, "A", 2)]
        )

    def test_insert_option_in_middle(self):
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            {
                "options": [
                    {"id": self.a.id, "text_uz": "A", "is_correct": True},
                    {"text_uz": "Yangi", "is_correct": False},
                    {"id": self.b.id, "text_uz": "B", "is_correct": False},
                    {"id": self.c.id, "text_uz": "C", "is_correct": False},
                ]
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.q.options.count(), 4)
        self.assertEqual(
            [o.text_uz for o in self.q.options.order_by("sort_order")],
            ["A", "Yangi", "B", "C"],
        )

    def test_remove_option_from_middle(self):
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            self._options_payload(self.a, self.c),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([o.text_uz for o in self.q.options.order_by("sort_order")], ["A", "C"])

    def test_delete_unused_question(self):
        res = self.client.delete(f"/api/questions/{self.q.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Question.objects.filter(pk=self.q.id).exists())

    def test_cannot_remove_option_already_selected_by_student(self):
        from practice.models import PracticeAnswer, PracticeSession

        session = PracticeSession.objects.create(
            user=self.student,
            subject=self.subject,
            question_count=1,
            status=PracticeSession.Status.FINISHED,
        )
        PracticeAnswer.objects.create(
            session=session, question=self.q, selected_option=self.c, is_correct=False
        )
        res = self.client.patch(
            f"/api/questions/{self.q.id}/",
            self._options_payload(self.a, self.b),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("options", res.data)
        # The question must be left untouched, not half-rewritten.
        self.assertEqual(self.q.options.count(), 3)
        self.assertEqual(
            [o.text_uz for o in self.q.options.order_by("sort_order")],
            ["A", "B", "C"],
        )

    def test_cannot_delete_question_used_in_session(self):
        from practice.models import PracticeAnswer, PracticeSession

        session = PracticeSession.objects.create(
            user=self.student, subject=self.subject, question_count=1
        )
        PracticeAnswer.objects.create(
            session=session, question=self.q, selected_option=self.a, is_correct=True
        )
        res = self.client.delete(f"/api/questions/{self.q.id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Question.objects.filter(pk=self.q.id).exists())