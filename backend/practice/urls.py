from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .stats import MistakesView, StatsSummaryView
from .views import (
    CertificateListCreateView,
    CertificateVerifyView,
    LeaderboardView,
    PracticeSessionViewSet,
)
from .weak_skills import (
    WeakSkillPracticeView,
    WeakSkillRadarView,
    WeakSkillSubjectView,
)

router = SimpleRouter()
router.register("sessions", PracticeSessionViewSet, basename="session")

urlpatterns = [
    path("", include(router.urls)),
    path("weak-skills/", WeakSkillRadarView.as_view(), name="weak-skills"),
    path(
        "weak-skills/practice/",
        WeakSkillPracticeView.as_view(),
        name="weak-skills-practice",
    ),
    path(
        "weak-skills/<str:subject>/",
        WeakSkillSubjectView.as_view(),
        name="weak-skills-subject",
    ),
    path("stats/summary/", StatsSummaryView.as_view(), name="stats-summary"),
    path("stats/mistakes/", MistakesView.as_view(), name="stats-mistakes"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path(
        "certificates/",
        CertificateListCreateView.as_view(),
        name="certificate-list",
    ),
    path(
        "certificates/<str:serial>/",
        CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
]