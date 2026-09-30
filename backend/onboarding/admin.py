from django.contrib import admin

from .models import OnboardingPlan, OnboardingProfile


class OnboardingPlanInline(admin.TabularInline):
    model = OnboardingPlan
    extra = 0
    fields = ("start_date", "weak_subject_ids", "created_at")
    readonly_fields = ("start_date", "weak_subject_ids", "created_at")
    can_delete = True


@admin.register(OnboardingProfile)
class OnboardingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "direction",
        "level",
        "daily_minutes",
        "exam_date",
        "completed",
        "skipped",
        "created_at",
    )
    list_filter = ("completed", "skipped", "level", "exam_date")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    filter_horizontal = ("subjects",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [OnboardingPlanInline]

    def has_add_permission(self, request):
        # Profiles are created by the wizard, never by hand.
        return False


@admin.register(OnboardingPlan)
class OnboardingPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "start_date", "weak_subject_ids", "created_at")
    list_filter = ("start_date", "created_at")
    search_fields = ("profile__user__username",)
    readonly_fields = ("profile", "start_date", "days", "weak_subject_ids", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
