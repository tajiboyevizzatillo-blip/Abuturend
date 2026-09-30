from django.urls import path

from .views import CheckoutView, PaymentStatusView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="payments-checkout"),
    path("<int:pk>/", PaymentStatusView.as_view(), name="payments-status"),
]
