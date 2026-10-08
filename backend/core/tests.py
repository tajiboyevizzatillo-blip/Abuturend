import json
import unittest
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import resolve

from rest_framework import status
from rest_framework.test import APITestCase

from core.views import API_ENDPOINTS


def _normalise(path: str) -> str:
    """Reduce a path to a comparable shape.

    Documentation writes ``/api/subjects/{slug}/``; the URLconf produces
    ``api/subjects/<slug:slug>/`` with a converter. Both must reduce to
    ``/api/subjects/*/`` for the comparison to be meaningful.
    """
    import re

    # Order matters: the DRF router emits regex-style named groups
    # `(?P<pk>[^/.]+)`, which must be collapsed *before* the plain `<name>`
    # converter rule runs — otherwise `<pk>[^/.` is mistaken for one group.
    out = re.sub(r"\(\?P<[^>]+>[^)]*\)", "*", path)
    out = re.sub(r"<[^:>]+:([^>]+)>", r"{\1}", out)
    out = re.sub(r"<[^>]+>", "*", out)
    out = re.sub(r"\{[^}]+\}", "*", out)
    out = out.replace("^", "").replace("$", "").replace("\\", "")
    if not out.startswith("/"):
        out = "/" + out
    return out


class ApiRootTests(APITestCase):
    def test_api_root_reports_endpoints(self):
        res = self.client.get("/api/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["version"], "1.0")
        self.assertGreater(len(res.data["endpoints"]), 10)

    def test_endpoint_catalog_is_in_sync_with_urlconf(self):
        """Every documented path must resolve; docs cannot rot silently."""
        for entry in API_ENDPOINTS:
            path = entry["path"]
            resolvable = path.replace("{slug}", "matematika").replace("{id}", "1")
            try:
                match = resolve(resolvable)
            except Exception as exc:  # noqa: BLE001 - assert message below
                self.fail(f"{path} no longer resolves: {exc}")

    def test_every_router_action_is_documented(self):
        """The reverse direction: a new endpoint must be added to the catalogue.

        The test above only proves documented -> resolvable, so a new viewset
        action (e.g. the abandon endpoint) could ship undocumented and the
        self-describing ``GET /api/`` would quietly become incomplete.
        """
        import re

        from django.urls import get_resolver

        documented = {
            _normalise(entry["path"]) for entry in API_ENDPOINTS
        }
        undocumented = []
        resolver = get_resolver()

        def walk(patterns, prefix=""):
            for p in patterns:
                if hasattr(p, "url_patterns"):
                    walk(p.url_patterns, prefix + str(p.pattern))
                    continue
                route = prefix + str(p.pattern)
                if not route.startswith("api/"):
                    continue
                norm = _normalise(route)
                if norm not in documented:
                    undocumented.append(norm)

        walk(resolver.url_patterns)
        self.assertEqual(
            undocumented,
            [],
            "endpoint(s) exist in the URLconf but are missing from "
            "core.views.API_ENDPOINTS",
        )

    def test_health_ok(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "ok")


class SecurityHeadersTests(SimpleTestCase):
    def test_headers_present_on_api_response(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("Permissions-Policy", res.headers)
        self.assertEqual(res.headers["X-Frame-Options"], "DENY")
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")


def _mojibake_runs(text: str) -> list[str]:
    """Runs of characters that are UTF-8 bytes misread as CP1251.

    A file written through the wrong Windows code page keeps its bytes but the
    characters arrive doubled: every Cyrillic letter of `Радар` becomes a
    three-character fragment instead of one. The corruption is invisible to
    `json.loads` and to every linter — the strings simply reach the user
    garbled — so it has to be detected structurally.

    Any run of non-ASCII characters that survives a `cp1251 -> utf-8` round trip
    is mojibake by definition: genuine Uzbek Latin, Russian and real typography
    (`—`, `·`, `•`, `«»`) never decode as UTF-8 under CP1251.
    """
    found = []
    run: list[str] = []
    for ch in [*text, "\0"]:
        if ch != "\0" and ord(ch) > 127:
            run.append(ch)
            continue
        if run:
            chunk = "".join(run)
            run = []
            try:
                fixed = chunk.encode("cp1251").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if fixed != chunk:
                found.append(chunk)
    return found


class TextEncodingTests(SimpleTestCase):
    """Guard the user-facing copy against double-encoded (mojibake) text."""

    TESTS_DIR = Path(__file__).resolve().parents[2]
    # The backend image ships `backend/` only, so the i18n guards stand down
    # there instead of failing on a missing directory.
    HAS_FRONTEND = (TESTS_DIR / "frontend" / "messages").is_dir()

    @unittest.skipUnless(HAS_FRONTEND, "frontend/messages is not available")
    def test_i18n_messages_are_not_double_encoded(self):
        """The Russian translation is the most exposed file for this class of bug.

        A whole section (`weakSkills`) and two other strings were committed as
        double-encoded UTF-8, so the ru locale rendered as doubled Cyrillic
        fragments while every check stayed green.
        """
        for name in ("uz", "ru", "en"):
            path = self.TESTS_DIR / "frontend" / "messages" / f"{name}.json"
            text = path.read_text(encoding="utf-8")
            self.assertEqual(_mojibake_runs(text), [], f"{name}.json contains mojibake")

    @unittest.skipUnless(HAS_FRONTEND, "frontend/messages is not available")
    def test_i18n_messages_have_identical_key_sets(self):
        def keys(node, prefix=""):
            out = set()
            for key, value in node.items():
                path = f"{prefix}{key}"
                if isinstance(value, dict):
                    out |= keys(value, path + ".")
                else:
                    out.add(path)
            return out

        messages = self.TESTS_DIR / "frontend" / "messages"
        base = keys(json.loads((messages / "uz.json").read_text(encoding="utf-8")))
        for name in ("ru", "en"):
            other = keys(
                json.loads((messages / f"{name}.json").read_text(encoding="utf-8"))
            )
            self.assertEqual(base - other, set(), f"{name}.json is missing keys")
            self.assertEqual(other - base, set(), f"{name}.json has extra keys")

    @unittest.skipUnless(HAS_FRONTEND, "frontend/messages is not available")
    def test_uz_messages_contain_no_cyrillic_letters(self):
        """Uzbek is written in Latin; a stray `а` from a bad copy/paste is invisible."""
        text = (self.TESTS_DIR / "frontend" / "messages" / "uz.json").read_text(
            encoding="utf-8"
        )
        cyrillic = sorted({ch for ch in text if 0x400 <= ord(ch) <= 0x4FF})
        self.assertEqual(cyrillic, [], f"uz.json contains Cyrillic letters: {cyrillic}")

    def test_telegram_copy_is_not_double_encoded(self):
        from telegrambot.services import HELP_TEXT, WELCOME_TEXT

        for label, text in (("WELCOME_TEXT", WELCOME_TEXT), ("HELP_TEXT", HELP_TEXT)):
            self.assertEqual(_mojibake_runs(text), [], f"{label} contains mojibake")

    def test_telegram_welcome_and_help_use_real_typography(self):
        """The corruption replaced `🤖`/`•` with look-alike junk; pin the real glyphs."""
        from telegrambot.services import HELP_TEXT, WELCOME_TEXT

        for label, text in (("WELCOME_TEXT", WELCOME_TEXT), ("HELP_TEXT", HELP_TEXT)):
            self.assertIn("🤖", text, f"{label} lost its emoji")
            self.assertIn("•", text, f"{label} lost its bullets")
            self.assertIn("—", text, f"{label} lost its em dashes")