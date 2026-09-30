import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Subject, Topic
from questions.models import Question, QuestionOption


class PracticeSession(models.Model):
    class Mode(models.TextChoices):
        PRACTICE = "practice", "Mashq"
        EXAM = "exam", "Sinov imtihoni"

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "Jarayonda"
        FINISHED = "finished", "Yakunlangan"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="practice_sessions",
        on_delete=models.CASCADE,
    )
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.PRACTICE, db_index=True
    )
    # null = unified exam (umumiy imtihon): questions are sampled across
    # every subject instead of one.
    subject = models.ForeignKey(
        Subject,
        related_name="practice_sessions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    topic = models.ForeignKey(
        Topic, related_name="practice_sessions", on_delete=models.PROTECT, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    question_count = models.PositiveIntegerField(default=10)
    progress_index = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    incorrect_answers = models.PositiveIntegerField(default=0)
    # Exam time limit. Server-side deadline so a patched client cannot keep
    # answering after the countdown; practice sessions have no limit.
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        db_table = "practice_session"
        indexes = [
            models.Index(fields=["user", "started_at"], name="prac_session_user_started"),
            models.Index(fields=["user", "finished_at"], name="prac_session_user_finished"),
        ]

    def __str__(self):
        return f"{self.user} - {self.subject} ({self.mode})"


class Certificate(models.Model):
    """Server-issued result certificate for a finished unified exam.

    Two renderings of the same result: an international-style band (CEFR-ish
    grade) and a local-style pass/fail decision (60%+ passes). The serial is
    the public verification key — it carries no auth, so anyone holding it can
    confirm authenticity via GET /api/certificates/{serial}/.
    """

    class Style(models.TextChoices):
        INTERNATIONAL = "international", "Xalqaro"
        LOCAL = "local", "Mahalliy"

    session = models.ForeignKey(
        PracticeSession, related_name="certificates", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="certificates",
        on_delete=models.CASCADE,
    )
    serial = models.CharField(max_length=32, unique=True, db_index=True)
    style = models.CharField(max_length=16, choices=Style.choices)
    # Snapshot so renaming the account later never falsifies an issued document.
    full_name = models.CharField(max_length=150)
    score_percent = models.PositiveSmallIntegerField()
    correct_answers = models.PositiveIntegerField()
    question_count = models.PositiveIntegerField()
    grade = models.CharField(max_length=8)
    passed = models.BooleanField(default=False)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        db_table = "practice_certificate"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "style"], name="uniq_certificate_session_style"
            )
        ]

    def __str__(self):
        return f"{self.serial} ({self.score_percent}%)"

    @staticmethod
    def band_for(percent: int) -> str:
        """International-style band (toifa) computed server-side."""
        if percent >= 90:
            return "C1"
        if percent >= 75:
            return "B2"
        if percent >= 60:
            return "B1"
        if percent >= 45:
            return "A2"
        return "A1"

    @staticmethod
    def new_serial() -> str:
        alphabet = string.ascii_uppercase + string.digits
        year = timezone.localdate().year
        while True:
            token = "".join(secrets.choice(alphabet) for _ in range(6))
            serial = f"ABT-{year}-{token}"
            if not Certificate.objects.filter(serial=serial).exists():
                return serial


class PracticeAnswer(models.Model):
    session = models.ForeignKey(
        PracticeSession, related_name="answers", on_delete=models.CASCADE
    )
    question = models.ForeignKey(
        Question, related_name="practice_answers", on_delete=models.PROTECT
    )
    selected_option = models.ForeignKey(
        QuestionOption,
        related_name="selections",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        db_table = "practice_answer"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "question"], name="uniq_session_question"
            )
        ]
        indexes = [
            models.Index(fields=["session", "is_correct"], name="prac_answer_session_correct"),
            models.Index(fields=["answered_at"], name="prac_answer_answered_at"),
        ]

    def __str__(self):
        return f"{self.session_id} -> {self.question_id}"