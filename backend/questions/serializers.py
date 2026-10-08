from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import serializers

from .models import Question, QuestionOption


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text_uz", "text_ru", "text_en", "is_correct", "sort_order"]
        extra_kwargs = {"id": {"required": False, "read_only": False}}


def _option_dicts(instances):
    return [
        {
            "id": o.id,
            "text_uz": o.text_uz,
            "text_ru": o.text_ru,
            "text_en": o.text_en,
            "is_correct": o.is_correct,
            "sort_order": o.sort_order,
        }
        for o in instances
    ]


def _renumber(options):
    for idx, opt in enumerate(options):
        opt["sort_order"] = idx
    return options


# sort_order is a PositiveIntegerField, so the temporary parking slot used while
# re-syncing a question's options has to be high and positive rather than negative.
# Real sort orders are tiny, renumbered from 0 on every write.
_PARK_BASE = 1_000_000


class QuestionFullSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "subject",
            "topic",
            "subtopic",
            "text_uz",
            "text_ru",
            "text_en",
            "question_type",
            "difficulty",
            "explanation_uz",
            "explanation_ru",
            "explanation_en",
            "source_type",
            "is_official",
            "is_verified",
            "status",
            "created_by",
            "options",
            "created_at",
            "updated_at",
        ]
        # is_official / is_verified are review decisions, not client input: a teacher
        # that could write them could self-certify a hand-written item as an
        # official DTM question with no verification. They are read-only over the
        # API and set by staff through the admin, which is where they belong.
        #
        # ``status`` deliberately stays writable: publishing and archiving your
        # own questions is the teacher's core workflow. It is safe because
        # CanManageQuestions.has_object_permission confines a plain teacher to
        # questions they authored.
        read_only_fields = ["created_by", "is_official", "is_verified"]

    def validate(self, attrs):
        options = attrs.get("options")
        if options is None:
            if self.instance is None:
                raise serializers.ValidationError({"options": "Variantlar majburiy."})
            options = _option_dicts(self.instance.options.all())
        options = _renumber(options)
        attrs["options"] = options
        correct = [o for o in options if o.get("is_correct")]
        if not correct:
            raise serializers.ValidationError(
                {"options": "Kamida bitta to'g'ri javob bo'lishi kerak."}
            )
        qtype = attrs.get("question_type") or (
            self.instance.question_type if self.instance else "single"
        )
        if qtype == "single" and len(correct) > 1:
            raise serializers.ValidationError(
                {"options": "Bitta to'g'ri javobli savolda faqat bitta variant to'g'ri bo'lishi kerak."}
            )
        if len(options) < 2:
            raise serializers.ValidationError({"options": "Kamida 2 ta variant kerak."})
        return attrs

    def create(self, validated_data):
        options = validated_data.pop("options", [])
        validated_data["created_by"] = self.context["request"].user
        with transaction.atomic():
            question = Question.objects.create(**validated_data)
            self._sync_options(question, options)
        return question

    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if options is not None:
                self._sync_options(instance, options)
        return instance

    def _sync_options(self, question, options):
        """Persist the submitted option list onto ``question``.

        ``QuestionOption`` carries a UNIQUE (question, sort_order) constraint, so
        the final positions cannot be written naively: reordering two options, or
        inserting/removing one in the middle, momentarily assigns a sort_order that
        a sibling still holds and used to surface as an unhandled IntegrityError
        (HTTP 500) from the teacher UI.

        Every existing option is therefore first parked on a private high slot, and
        only then moved to its final index once nothing in the question can collide
        with it. All of them are parked, not just the ones the payload keeps: an
        option the teacher removed still occupies its old slot until phase 3
        deletes it, and would otherwise collide with the survivor that inherits
        that index.
        """
        parked = {obj.pk: obj for obj in question.options.all()}

        # Phase 1 — park all options on unique, out-of-range slots.
        for offset, obj in enumerate(parked.values(), start=1):
            obj.sort_order = _PARK_BASE + offset
            obj.save(update_fields=["sort_order"])

        # Phase 2 — apply the payload (final sort_order included) and insert new
        # options. No sibling in this question holds a final slot yet. An id that
        # does not belong to this question is ignored rather than trusted.
        kept = []
        for opt in options:
            opt_id = opt.get("id")
            obj = parked.get(opt_id) if opt_id else None
            if obj is None:
                obj = QuestionOption(question=question)
            for key, value in opt.items():
                if key != "id":
                    setattr(obj, key, value)
            obj.save()
            kept.append(obj.id)

        # Phase 3 — drop the options the teacher removed. Students' recorded
        # answers protect their option, so surface that as a field error rather
        # than a 500.
        try:
            with transaction.atomic():
                question.options.exclude(pk__in=kept).delete()
        except ProtectedError:
            raise serializers.ValidationError(
                {
                    "options": (
                        "Bu variantni o'chirib bo'lmaydi: u allaqachon abituriyentlar "
                        "topshirgan testlarda tanlangan. Variantni o'zgartirish "
                        "yoki savolni arxivlash mumkin."
                    )
                }
            )


class QuestionOptionBrowse(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text_uz", "text_ru", "text_en", "sort_order"]


class QuestionBrowseSerializer(serializers.ModelSerializer):
    options = QuestionOptionBrowse(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "subject",
            "topic",
            "subtopic",
            "text_uz",
            "text_ru",
            "text_en",
            "question_type",
            "difficulty",
            "options",
        ]