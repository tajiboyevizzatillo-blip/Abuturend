from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from catalog.models import Subject
from universities.models import Direction

from .models import OnboardingPlan, OnboardingProfile

MIN_DAILY_MINUTES = 15
MAX_DAILY_MINUTES = 480
# The plan spans at most a week, so a date further out than this is not useful.
MAX_EXAM_DAYS = 730


class OnboardingProfileSerializer(serializers.ModelSerializer):
    direction = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()
    days_left = serializers.IntegerField(read_only=True)
    needs_onboarding = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingProfile
        fields = [
            "id",
            "direction",
            "subjects",
            "exam_date",
            "daily_minutes",
            "level",
            "completed",
            "skipped",
            "days_left",
            "needs_onboarding",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "completed", "skipped", "created_at", "updated_at"]

    def get_direction(self, obj):
        if obj.direction_id is None:
            return None
        d = obj.direction
        return {
            "id": d.id,
            "code": d.code,
            "name_uz": d.name_uz,
            "name_ru": d.name_ru,
            "name_en": d.name_en,
            "university": {
                "slug": d.university.slug,
                "name_uz": d.university.name_uz,
                "name_ru": d.university.name_ru,
                "name_en": d.university.name_en,
            },
        }

    def get_subjects(self, obj):
        return [
            {
                "id": s.id,
                "slug": s.slug,
                "code": s.code,
                "name_uz": s.name_uz,
                "name_ru": s.name_ru,
                "name_en": s.name_en,
            }
            for s in obj.subjects.all()
        ]

    def get_needs_onboarding(self, obj) -> bool:
        return obj.needs_onboarding()


class OnboardingSubmitSerializer(serializers.Serializer):
    """Wizard answers. ``direction`` is optional: a student may only want a
    study plan without committing to a university."""

    direction = serializers.PrimaryKeyRelatedField(
        queryset=Direction.active.all(), required=False, allow_null=True
    )
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.active.all(), many=True, allow_empty=False
    )
    exam_date = serializers.DateField(required=False, allow_null=True)
    daily_minutes = serializers.IntegerField(
        min_value=MIN_DAILY_MINUTES, max_value=MAX_DAILY_MINUTES, default=60
    )
    level = serializers.ChoiceField(
        choices=OnboardingProfile.Level.choices, default=OnboardingProfile.Level.BEGINNER
    )

    def validate_exam_date(self, value):
        if value is None:
            return value
        today = timezone.localdate()
        if value <= today:
            raise serializers.ValidationError("Imtihon sanasi kelajakda bo'lishi kerak.")
        if value > today + timedelta(days=MAX_EXAM_DAYS):
            raise serializers.ValidationError("Imtihon sanasi juda uzoq ko'rinadi.")
        return value

    def validate(self, attrs):
        subjects = attrs.get("subjects") or []
        if len(subjects) < 1:
            raise serializers.ValidationError(
                {"subjects": "Kamida bitta fan tanlang."}
            )
        if len(set(s.id for s in subjects)) != len(subjects):
            raise serializers.ValidationError(
                {"subjects": "Fanlar ro'yxatida takrorlanish bor."}
            )
        # A direction's own subject list is a recommendation, not a filter:
        # forcing it would silently override the student's choice.
        return attrs


class PlanDayItemSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    subject = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField(allow_null=True)
    topic = serializers.SerializerMethodField()
    questions = serializers.IntegerField()
    minutes = serializers.IntegerField()

    def get_subject(self, obj):
        return _subject_brief(obj["subject_id"])

    def get_topic(self, obj):
        return _topic_brief(obj.get("topic_id"))


def _subject_brief(subject_id):
    if subject_id is None:
        return None
    subject = Subject.objects.filter(pk=subject_id).first()
    if subject is None:
        return None
    return {
        "id": subject.id,
        "slug": subject.slug,
        "code": subject.code,
        "name_uz": subject.name_uz,
        "name_ru": subject.name_ru,
        "name_en": subject.name_en,
    }


def _topic_brief(topic_id):
    from catalog.models import Topic

    if topic_id is None:
        return None
    topic = Topic.objects.filter(pk=topic_id).select_related("subject").first()
    if topic is None:
        return None
    return {
        "id": topic.id,
        "slug": topic.slug,
        "subject_id": topic.subject_id,
        "name_uz": topic.name_uz,
        "name_ru": topic.name_ru,
        "name_en": topic.name_en,
    }


class OnboardingPlanSerializer(serializers.ModelSerializer):
    profile = OnboardingProfileSerializer(read_only=True)
    days = serializers.SerializerMethodField()
    total_questions = serializers.IntegerField(read_only=True)
    weak_subjects = serializers.SerializerMethodField()
    today = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingPlan
        fields = [
            "id",
            "profile",
            "start_date",
            "days",
            "total_questions",
            "weak_subjects",
            "today",
            "created_at",
        ]
        read_only_fields = fields

    def get_days(self, obj):
        return [
            {
                "day": day.get("day"),
                "date": day.get("date"),
                "questions": day.get("questions", 0),
                "minutes": day.get("minutes", 0),
                "items": PlanDayItemSerializer(day.get("items", []), many=True).data,
            }
            for day in obj.days
        ]

    def get_weak_subjects(self, obj):
        return [_subject_brief(sid) for sid in obj.weak_subject_ids or []]

    def get_today(self, obj):
        """Index of today's plan day (1-based), ``None`` when the plan is over."""
        today = timezone.localdate()
        delta = (today - obj.start_date).days + 1
        if delta < 1 or delta > len(obj.days):
            return None
        return delta
