from django.conf import settings
from django.db import models

from catalog.models import Subject, Subtopic, Topic
from core.models import ActiveManager, TimeStampedModel


class Question(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        PUBLISHED = "published", "Chop etilgan"
        ARCHIVED = "archived", "Arxivlangan"

    class Difficulty(models.IntegerChoices):
        EASY = 1, "Oson"
        MEDIUM = 2, "O'rta"
        HARD = 3, "Qiyin"

    class SourceType(models.TextChoices):
        DTM = "dtm", "DTM rasmiy"
        BMB = "bmb", "BMB rasmiy"
        CUSTOM = "custom", "O'qituvchi tuzgan"
        UNKNOWN = "unknown", "Noma'lum"

    subject = models.ForeignKey(
        Subject, related_name="questions", on_delete=models.PROTECT
    )
    topic = models.ForeignKey(
        Topic, related_name="questions", on_delete=models.PROTECT, null=True, blank=True
    )
    subtopic = models.ForeignKey(
        Subtopic,
        related_name="questions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    text_uz = models.TextField()
    text_ru = models.TextField(blank=True, default="")
    text_en = models.TextField(blank=True, default="")

    question_type = models.CharField(
        max_length=16,
        choices=[("single", "Bitta to'g'ri javob"), ("multiple", "Bir nechta to'g'ri javob")],
        default="single",
    )
    difficulty = models.PositiveSmallIntegerField(
        choices=Difficulty.choices, default=Difficulty.MEDIUM, db_index=True
    )
    explanation_uz = models.TextField(blank=True, default="")
    explanation_ru = models.TextField(blank=True, default="")
    explanation_en = models.TextField(blank=True, default="")

    source_type = models.CharField(
        max_length=16,
        choices=SourceType.choices,
        default=SourceType.UNKNOWN,
    )
    is_official = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_questions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    objects = models.Manager()

    class Meta:
        ordering = ["-id"]
        db_table = "questions_question"
        indexes = [
            # Zaif mavzular radari (practice/weak_skills.py) mashq uchun
            # savollarni shu tartibda filtrlaydi: topic_id IN (...) AND
            # is_active AND status. FK ustuniga Django o'z indeksini qo'yadi,
            # lekin birinchi ustun topic bo'lganda filtr to'g'ridan-to'g'ri
            # indeksdan foydalanadi.
            models.Index(fields=["topic", "is_active"], name="questions_topic_active"),
        ]

    def __str__(self):
        return self.text_uz[:60]


class QuestionOption(models.Model):
    question = models.ForeignKey(
        Question, related_name="options", on_delete=models.CASCADE
    )
    text_uz = models.TextField()
    text_ru = models.TextField(blank=True, default="")
    text_en = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        db_table = "questions_option"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "sort_order"],
                name="uniq_option_question_order",
            )
        ]

    def __str__(self):
        return self.text_uz[:60]