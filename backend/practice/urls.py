from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .stats import MistakesView, StatsSummaryView
from .views import (
    CertificateListCreateView,
    CertificateVerifyView,
    LeaderboardView,
    PracticeSessionViewSet,
)

router = SimpleRouter()
router.register("sessions", PracticeSessionViewSet, basename="session")

urlpatterns = [
    path("", include(router.urls)),
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