from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "provider", "amount_uzs", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("user__username", "gateway_ref")
    readonly_fields = ("meta", "gateway_ref", "paid_at", "created_at", "updated_at")
