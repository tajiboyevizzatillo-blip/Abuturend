from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import User


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf_url = "/api/auth/csrf/"
        # Auth endpoints are rate limited (register is 5/hour); the throttle cache
        # outlives a single test, so reset it or unrelated tests 429 each other.
        cache.clear()

    def _csrf_token(self):
        self.client.get(self.csrf_url)
        return self.client.cookies["csrftoken"].value

    def _post(self, path, data):
        token = self._csrf_token()
        return self.client.post(
            path, data, format="json", HTTP_X_CSRFTOKEN=token
        )

    def test_register_and_auto_login(self):
        res = self._post(
            "/api/auth/register/",
            {
                "username": "ali",
                "password": "StrongPass123!",
                "email": "ali@example.com",
                "role": "student",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="ali").exists())
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "ali")

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username="dupuser", password="x")
        res = self._post(
            "/api/auth/register/",
            {"username": "dupuser", "password": "StrongPass123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_rejected(self):
        # Django's validator set: too short, all-numeric, and a well-known common
        # password. The one-character case is the regression that mattered.
        for weak in ("1", "12345678", "password", "qwerty123"):
            with self.subTest(password=weak):
                res = self._post(
                    "/api/auth/register/",
                    {"username": f"weak{len(weak)}x", "password": weak},
                )
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("password", res.data)
        self.assertEqual(User.objects.filter(username__startswith="weak").count(), 0)

    def test_password_similar_to_username_rejected(self):
        res = self._post(
            "/api/auth/register/",
            {"username": "sardor123", "password": "sardor123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

    def test_change_password_rejects_weak_password(self):
        User.objects.create_user(username="kuchsiz", password="old-pass-1")
        self._post(
            "/api/auth/login/", {"username": "kuchsiz", "password": "old-pass-1"}
        )
        res = self._post(
            "/api/auth/change-password/",
            {"old_password": "old-pass-1", "new_password": "1"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)
        # The old password must still work: a rejected change must not lock the
        # user out.
        self.assertEqual(
            self._post(
                "/api/auth/login/", {"username": "kuchsiz", "password": "old-pass-1"}
            ).status_code,
            status.HTTP_200_OK,
        )

    def test_login_and_logout_flow(self):
        User.objects.create_user(username="vali", password="StrongPass123!")
        res = self._post(
            "/api/auth/login/",
            {"username": "vali", "password": "StrongPass123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "vali")

        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self._post("/api/auth/logout/", {})
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        res = self.client.get("/api/auth/me/")
        self.assertIn(res.status_code, (401, 403))

    def test_login_wrong_password(self):
        User.objects.create_user(username="qayum", password="right-pass-1")
        res = self._post(
            "/api/auth/login/",
            {"username": "qayum", "password": "wrong-pass"},
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_auth(self):
        res = self.client.get("/api/auth/me/")
        self.assertIn(res.status_code, (401, 403))

    def test_change_password(self):
        User.objects.create_user(username="soli", password="old-pass-1")
        self._post("/api/auth/login/", {"username": "soli", "password": "old-pass-1"})
        res = self._post(
            "/api/auth/change-password/",
            {"old_password": "old-pass-1", "new_password": "new-pass-1"},
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self._post("/api/auth/logout/", {})
        res = self._post("/api/auth/login/", {"username": "soli", "password": "new-pass-1"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_teacher_role_only_via_admin(self):
        # An anonymous user cannot register as teacher through the public API.
        res = self._post(
            "/api/auth/register/",
            {"username": "teach", "password": "StrongPass123!", "role": "teacher"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_self_promote_role(self):
        User.objects.create_user(username="troll", password="StrongPass123!")
        self._post(
            "/api/auth/login/",
            {"username": "troll", "password": "StrongPass123!"},
        )
        token = self._csrf_token()
        res = self.client.patch(
            "/api/auth/me/",
            {"role": "admin"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user = User.objects.get(username="troll")
        self.assertEqual(user.role, User.Role.STUDENT)

    def test_login_without_csrf_rejected(self):
        # csrf_protect on LoginView blocks the classic login-CSRF form post.
        User.objects.create_user(username="nocsrf", password="StrongPass123!")
        res = self.client.post(
            "/api/auth/login/",
            {"username": "nocsrf", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_without_csrf_rejected(self):
        res = self.client.post(
            "/api/auth/register/",
            {"username": "nocsrf2", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        cache.clear()

    def _csrf_token(self):
        self.client.get("/api/auth/csrf/")
        return self.client.cookies["csrftoken"].value

    def _post(self, path, data):
        return self.client.post(
            path,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=self._csrf_token(),
        )

    def test_request_sends_mail_and_never_enumerates(self):
        from django.core import mail

        User.objects.create_user(
            username="tokhir", password="StrongPass123!", email="tokhir@example.com"
        )
        res = self._post(
            "/api/auth/password-reset/", {"email": "tokhir@example.com"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("uid=", mail.outbox[0].body)
        self.assertIn("token=", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["tokhir@example.com"])

        # Unknown email gets the exact same answer and sends nothing.
        ghost = self._post("/api/auth/password-reset/", {"email": "ghost@example.com"})
        self.assertEqual(ghost.status_code, status.HTTP_200_OK)
        self.assertEqual(ghost.data, res.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_confirm_sets_new_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.core import mail
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        user = User.objects.create_user(
            username="nilufar", password="OldPass123!", email="n@example.com"
        )
        self._post("/api/auth/password-reset/", {"email": "n@example.com"})
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        res = self._post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "NewPass123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            self._post(
                "/api/auth/login/", {"username": "nilufar", "password": "NewPass123!"}
            ).status_code
            == status.HTTP_200_OK
        )

        # The same link cannot be replayed after the password changed.
        replay = self._post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "AnotherPass123!"},
        )
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", replay.data)

    def test_confirm_rejects_garbage_token(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        user = User.objects.create_user(
            username="badtok", password="StrongPass123!", email="b@example.com"
        )
        res = self._post(
            "/api/auth/password-reset/confirm/",
            {
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": "not-a-real-token",
                "new_password": "NewPass123!",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self._post(
            "/api/auth/password-reset/confirm/",
            {"uid": "bGVnYWw=", "token": "x", "new_password": "NewPass123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)