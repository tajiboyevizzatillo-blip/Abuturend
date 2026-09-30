import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf": get_token(request)})


# Anonymous login/register POSTs are otherwise exempt (DRF marks APIViews
# csrf_exempt and SessionAuthentication only enforces CSRF once authenticated),
# which allows login-CSRF: silently logging a victim into an attacker's account.
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        login(request, user)
        return Response(
            UserSerializer(user).data, status=status.HTTP_201_CREATED
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                {"detail": serializer.errors}, status=status.HTTP_401_UNAUTHORIZED
            )
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "password"

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        login(request, user)  # re-auth without invalidating the session
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    """Start a password reset. Always answers 200 to avoid email enumeration."""

    permission_classes = [AllowAny]
    throttle_scope = "password"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f"{settings.FRONTEND_BASE_URL.rstrip('/')}/uz/reset-password/"
                f"?uid={uid}&token={token}"
            )
            body = (
                f"Parolni tiklash uchun havola:\n{reset_url}\n\n"
                f"Ссылка для сброса пароля:\n{reset_url}\n\n"
                f"Password reset link:\n{reset_url}"
            )
            try:
                send_mail(
                    "Parolni tiklash / Сброс пароля / Password reset",
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
            except Exception:
                # Never 500 on a broken mailer; the response must stay uniform.
                logger.exception("Parol tiklash xati yuborilmadi")
        return Response(
            {"detail": "Agar bu email ro'yxatdan o'tgan bo'lsa, tiklash havolasi yuborildi."}
        )


class PasswordResetConfirmView(APIView):
    """Consume uid+token from the emailed link and set a new password."""

    permission_classes = [AllowAny]
    throttle_scope = "password"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user_id = force_str(urlsafe_base64_decode(str(data["uid"])))
            user = User.objects.get(pk=user_id, is_active=True)
        except (ValueError, TypeError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
            raise_invalid_token()
        if not default_token_generator.check_token(user, data["token"]):
            raise_invalid_token()
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Parol yangilandi."})


def raise_invalid_token():
    from rest_framework.exceptions import ValidationError

    raise ValidationError({"token": "Tiklash havolasi yaroqsiz yoki muddati tugagan."})