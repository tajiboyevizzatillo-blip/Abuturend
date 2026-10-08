from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from .models import Question
from .permissions import CanManageQuestions
from .serializers import QuestionBrowseSerializer, QuestionFullSerializer


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.select_related("subject", "topic", "subtopic")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["subject", "topic", "subtopic", "difficulty", "status"]
    ordering_fields = ["id", "difficulty", "created_at", "updated_at"]
    ordering = ["-created_at"]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        perms = [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            perms.append(CanManageQuestions())
        return perms

    def get_serializer_class(self):
        user = self.request.user
        if user.is_staff or user.role in ("teacher", "admin"):
            return QuestionFullSerializer
        return QuestionBrowseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or user.role in ("teacher", "admin"):
            qs = qs.prefetch_related("options")
            if not (user.is_staff or user.is_superuser or user.role == "admin"):
                # Plain teachers manage only their own rows: their drafts plus
                # everything already published. Imported questions with no
                # author (created_by is NULL) stay visible read-only, and
                # has_object_permission rejects writes to them.
                qs = qs.filter(
                    Q(created_by=user) | Q(status=Question.Status.PUBLISHED)
                )
            return qs
        return qs.filter(
            Q(is_active=True), Q(status=Question.Status.PUBLISHED)
        ).prefetch_related("options")

    def perform_destroy(self, instance):
        """Recorded answers protect a question, so explain instead of 500-ing."""
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {
                    "detail": (
                        "Bu savolni o'chirib bo'lmaydi: u allaqachon abituriyentlar "
                        "tomatilgan testlarda ishlatilgan. Savolni arxivlang "
                        "(status=archived) — u testlardan chiqariladi, lekin "
                        "ma'lumotlar saqlanadi."
                    )
                }
            )