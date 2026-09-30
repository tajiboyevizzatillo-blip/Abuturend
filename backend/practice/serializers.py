from django.db.models import Q
from rest_framework import serializers

from catalog.serializers import SubjectBriefSerializer
from questions.models import Question, QuestionOption
from questions.serializers import QuestionOptionBrowse

from .models import Certificate, PracticeAnswer, PracticeSession

PUBLISHED_ACTIVE = Q(is_active=True) & Q(status=Question.Status.PUBLISHED)


class PracticeStartSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(min_value=1, max_value=30, default=10)
    duration_minutes = serializers.IntegerField(
        min_value=1, max_value=240, required=False, allow_null=True
    )
    # Mistakes notebook (xatolar daftari): an explicit question list instead of
    # sampling a subject — lets a student re-drill exactly what they got wrong.
    question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
        max_length=30,
    )

    class Meta:
        model = PracticeSession
        fields = [
            "id",
            "mode",
            "subject",
            "topic",
            "question_count",
            "duration_minutes",
            "question_ids",
        ]
        read_only_fields = ["id"]

    def validate_question_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Savollar ro'yxatida takrorlanish bor.")
        found = set(
            Question.objects.filter(PUBLISHED_ACTIVE, id__in=value).values_list(
                "id", flat=True
            )
        )
        missing = [i for i in value if i not in found]
        if missing:
            raise serializers.ValidationError(
                "Ba'zi savollar topilmadi yoki hozircha mavjud emas."
            )
        return value

    def validate(self, attrs):
        topic = attrs.get("topic")
        subject = attrs.get("subject")
        question_ids = attrs.get("question_ids")
        if question_ids:
            if attrs.get("mode") != PracticeSession.Mode.PRACTICE:
                raise serializers.ValidationError(
                    {"mode": "Aniq savollar bilan faqat mashq rejimida mashq qilinadi."}
                )
            if subject is not None:
                raise serializers.ValidationError(
                    {"subject": "Savollar ro'yxati bilan fan tanlanmaydi."}
                )
            if topic is not None:
                raise serializers.ValidationError(
                    {"topic": "Savollar ro'yxati bilan mavzu tanlanmaydi."}
                )
        if topic is not None and subject is None:
            raise serializers.ValidationError(
                {"topic": "Mavzu uchun fan tanlash shart."}
            )
        if topic is not None and subject is not None and topic.subject_id != subject.id:
            raise serializers.ValidationError(
                {"topic": "Mavzu boshqa fanga tegishli."}
            )
        # A subject-less session is either the unified exam (umumiy imtihon) or
        # an explicit question list (mistakes notebook) — never random sampling.
        if (
            subject is None
            and not question_ids
            and attrs.get("mode") != PracticeSession.Mode.EXAM
        ):
            raise serializers.ValidationError(
                {"subject": "Fansiz sessiya faqat imtihon rejimida mavjud."}
            )
        return attrs


class CertificateSerializer(serializers.ModelSerializer):
    exam_finished_at = serializers.DateTimeField(
        source="session.finished_at", read_only=True
    )

    class Meta:
        model = Certificate
        fields = [
            "id",
            "serial",
            "style",
            "full_name",
            "score_percent",
            "correct_answers",
            "question_count",
            "grade",
            "passed",
            "issued_at",
            "exam_finished_at",
        ]
        read_only_fields = fields


class CertificateCreateSerializer(serializers.Serializer):
    session = serializers.PrimaryKeyRelatedField(
        queryset=PracticeSession.objects.all()
    )
    style = serializers.ChoiceField(choices=Certificate.Style.choices)

    def validate_session(self, session):
        request = self.context["request"]
        if session.user_id != request.user.pk:
            # Not yours: pretend it does not exist instead of confirming ids.
            raise serializers.ValidationError("Bunday sessiya topilmadi.")
        if session.status != PracticeSession.Status.FINISHED:
            raise serializers.ValidationError(
                "Sertifikat faqat yakunlangan imtihon uchun beriladi."
            )
        if session.subject_id is not None:
            raise serializers.ValidationError(
                "Sertifikat faqat umumiy imtihon (barcha fanlar) uchun beriladi."
            )
        return session


class SessionListSerializer(serializers.ModelSerializer):
    subject = SubjectBriefSerializer(read_only=True)
    topic_name_uz = serializers.CharField(source="topic.name_uz", default=None)
    topic_name_ru = serializers.CharField(source="topic.name_ru", default=None)
    topic_name_en = serializers.CharField(source="topic.name_en", default=None)
    unanswered = serializers.SerializerMethodField()
    score_percent = serializers.SerializerMethodField()
    correct_answers = serializers.SerializerMethodField()
    incorrect_answers = serializers.SerializerMethodField()

    class Meta:
        model = PracticeSession
        fields = [
            "id",
            "mode",
            "subject",
            "topic",
            "topic_name_uz",
            "topic_name_ru",
            "topic_name_en",
            "status",
            "question_count",
            "progress_index",
            "correct_answers",
            "incorrect_answers",
            "unanswered",
            "score_percent",
            "started_at",
            "finished_at",
        ]

    @staticmethod
    def _hide_running_score(obj) -> bool:
        # While an exam is in progress the running score is an answer oracle
        # (compare counts across requests to find the correct option).
        return (
            obj.mode == PracticeSession.Mode.EXAM
            and obj.status != PracticeSession.Status.FINISHED
        )

    def get_unanswered(self, obj) -> int:
        return obj.question_count - obj.progress_index

    def get_score_percent(self, obj):
        if self._hide_running_score(obj):
            return None
        if not obj.question_count:
            return 0
        return round((obj.correct_answers / obj.question_count) * 100)

    def get_correct_answers(self, obj):
        return None if self._hide_running_score(obj) else obj.correct_answers

    def get_incorrect_answers(self, obj):
        return None if self._hide_running_score(obj) else obj.incorrect_answers


class OptionWithAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text_uz", "text_ru", "text_en", "is_correct", "sort_order"]


class PracticeQuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionBrowse(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "text_uz",
            "text_ru",
            "text_en",
            "question_type",
            "difficulty",
            "options",
        ]


class PracticeAnswerInSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    option_id = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        session = self.context["session"]
        answer = (
            session.answers.filter(question_id=attrs["question_id"])
            .select_related("question")
            .first()
        )
        if answer is None:
            raise serializers.ValidationError(
                {"question_id": "Savol sessiyaga tegishli emas."}
            )
        # Re-answering the same question is allowed: exam mode lets a student go
        # back and change a choice until the session is finished. The session
        # counters are recomputed from the answers, so the swap stays consistent.
        attrs["practice_answer"] = answer
        return attrs


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    display_name = serializers.SerializerMethodField()
    finished_sessions = serializers.IntegerField()
    correct_answers = serializers.IntegerField()
    total_answered = serializers.IntegerField()
    accuracy_percent = serializers.SerializerMethodField()

    def get_display_name(self, obj) -> str:
        # Public leaderboard: never expose raw usernames (enumeration aid).
        if obj.first_name:
            return obj.first_name
        return f"{obj.username[:2]}***"

    def get_accuracy_percent(self, obj) -> int:
        if not obj.total_answered:
            return 0
        return round((obj.correct_answers / obj.total_answered) * 100)


class PracticeAnswerResultSerializer(serializers.Serializer):
    is_correct = serializers.BooleanField()
    # None when the question has no correct option at all (data-quality problem,
    # not a reason to fail the student's request).
    correct_option_id = serializers.IntegerField(allow_null=True)
    explanation_uz = serializers.CharField()
    explanation_ru = serializers.CharField()
    explanation_en = serializers.CharField()
    correct_count = serializers.IntegerField()
    total_count = serializers.IntegerField()