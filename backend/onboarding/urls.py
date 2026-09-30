from django.urls import path

from .views import OnboardingPlanView, OnboardingSkipView, OnboardingView

urlpatterns = [
    path("", OnboardingView.as_view(), name="onboarding"),
    path("plan/", OnboardingPlanView.as_view(), name="onboarding-plan"),
    path("skip/", OnboardingSkipView.as_view(), name="onboarding-skip"),
]
