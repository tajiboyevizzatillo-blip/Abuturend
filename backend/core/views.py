from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    data = {
        "status": "ok",
        "service": "abiturend-backend",
        "version": "1.0",
    }
    return Response(data)


# Living endpoint catalogue. `core.tests` asserts every entry still resolves,
# so the docs cannot silently rot out of sync with the router.
API_VERSION = "1.0"

API_ENDPOINTS = [
    {
        "path": "/api/",
        "method": "GET",
        "auth": "public",
        "purpose": "This index: discover every endpoint of the platform.",
    },
    {
        "path": "/api/health/",
        "method": "GET",
        "auth": "public",
        "purpose": "Service health probe for load balancers and monitoring.",
    },
    {
        "path": "/api/auth/csrf/",
        "method": "GET",
        "auth": "public",
        "purpose": "CSRF token for session-authenticated requests.",
    },
    {
        "path": "/api/auth/register/",
        "method": "POST",
        "auth": "public",
        "purpose": "Create a student account.",
    },
    {
        "path": "/api/auth/login/",
        "method": "POST",
        "auth": "public",
        "purpose": "Authenticate with a session cookie.",
    },
    {
        "path": "/api/auth/logout/",
        "method": "POST",
        "auth": "session",
        "purpose": "Destroy the active session.",
    },
    {
        "path": "/api/auth/me/",
        "method": "GET, PATCH",
        "auth": "session",
        "purpose": "Read or update the current user's profile.",
    },
    {
        "path": "/api/auth/change-password/",
        "method": "POST",
        "auth": "session",
        "purpose": "Update the current user's password.",
    },
    {
        "path": "/api/auth/password-reset/",
        "method": "POST",
        "auth": "public",
        "purpose": "Start a password reset; emails a uid+token link (always 200).",
    },
    {
        "path": "/api/auth/password-reset/confirm/",
        "method": "POST",
        "auth": "public",
        "purpose": "Consume the emailed uid+token and set a new password.",
    },
    {
        "path": "/api/subjects/",
        "method": "GET",
        "auth": "public",
        "purpose": "List subjects (question counts included).",
    },
    {
        "path": "/api/subjects/{slug}/",
        "method": "GET",
        "auth": "public",
        "purpose": "A single subject; nested topics with question counts embedded.",
    },
    {
        "path": "/api/subjects/{slug}/topics/",
        "method": "GET",
        "auth": "public",
        "purpose": "Active topics of a subject with their published question counts.",
    },
    {
        "path": "/api/topics/",
        "method": "GET",
        "auth": "public",
        "purpose": "List topics.",
    },
    {
        "path": "/api/topics/{id}/",
        "method": "GET",
        "auth": "public",
        "purpose": "Topic detail; nested subtopics embedded.",
    },
    {
        "path": "/api/questions/",
        "method": "GET, POST",
        "auth": "GET any authenticated, POST teacher/admin",
        "purpose": "Browse (students see only published; is_correct hidden) or manage the bank.",
    },
    {
        "path": "/api/questions/{id}/",
        "method": "GET, PUT, PATCH, DELETE",
        "auth": "write teacher/admin, GET student",
        "purpose": "Question detail; students never receive correct-answer flags.",
    },
    {
        "path": "/api/sessions/",
        "method": "GET, POST",
        "auth": "session",
        "purpose": "Create a practice/exam session (omit subject for a unified exam across all subjects; pass question_ids for the mistakes notebook), or list own sessions.",
    },
    {
        "path": "/api/sessions/{id}/",
        "method": "GET",
        "auth": "session",
        "purpose": "Session summary (status, progress, score so far).",
    },
    {
        "path": "/api/sessions/{id}/current/",
        "method": "GET",
        "auth": "session",
        "purpose": "Next unanswered question.",
    },
    {
        "path": "/api/sessions/{id}/questions/",
        "method": "GET",
        "auth": "session",
        "purpose": "All session questions (correct answers hidden) for exam navigation.",
    },
    {
        "path": "/api/sessions/{id}/answer/",
        "method": "POST",
        "auth": "session",
        "purpose": "Submit an answer; returns immediate feedback (correctness, explanation).",
    },
    {
        "path": "/api/sessions/{id}/finish/",
        "method": "POST",
        "auth": "session",
        "purpose": "Finish the session and receive the full score report.",
    },
    {
        "path": "/api/sessions/{id}/report/",
        "method": "GET",
        "auth": "session",
        "purpose": "Read-only question-by-question review for a session.",
    },
    {
        "path": "/api/certificates/",
        "method": "GET, POST",
        "auth": "session",
        "purpose": "List own certificates; issue one for a finished unified exam (style=international|local).",
    },
    {
        "path": "/api/certificates/{serial}/",
        "method": "GET",
        "auth": "public",
        "purpose": "Verify a certificate by its printed serial (ABT-YYYY-XXXXXX).",
    },
    {
        "path": "/api/universities/",
        "method": "GET",
        "auth": "public",
        "purpose": "University catalogue with available directions and entrance subjects.",
    },
    {
        "path": "/api/universities/{slug}/",
        "method": "GET",
        "auth": "public",
        "purpose": "A single university; nested directions embedded.",
    },
    {
        "path": "/api/directions/",
        "method": "GET",
        "auth": "public",
        "purpose": "Directions filterable by university slug or admission subject.",
    },
    {
        "path": "/api/directions/{id}/",
        "method": "GET",
        "auth": "public",
        "purpose": "A single direction with its entrance subjects.",
    },
    {
        "path": "/api/stats/summary/",
        "method": "GET",
        "auth": "session",
        "purpose": "Aggregated learner analytics: accuracy, streak, weekly activity, subject breakdown, weak topics, recent sessions.",
    },
    {
        "path": "/api/stats/mistakes/",
        "method": "GET",
        "auth": "session",
        "purpose": "Mistakes notebook (xatolar daftari): the student's wrongly answered questions with wrong counts and mastered flags.",
    },
    {
        "path": "/api/leaderboard/",
        "method": "GET",
        "auth": "public",
        "purpose": "Leaderboard of students by correct answers across finished sessions (?limit=1..50, default 10). Staff accounts are excluded.",
    },
    {
        "path": "/api/premium/plans/",
        "method": "GET",
        "auth": "public",
        "purpose": "Active subscription plans (free tier and PRO).",
    },
    {
        "path": "/api/premium/subscription/",
        "method": "GET",
        "auth": "session",
        "purpose": "The current user's subscription status and remaining free sessions today.",
    },
    {
        "path": "/api/premium/subscribe/",
        "method": "POST",
        "auth": "session",
        "purpose": "Activate the free tier instantly; paid tiers answer 402 with checkout_required (use /api/payments/checkout/).",
    },
    {
        "path": "/api/payments/checkout/",
        "method": "POST",
        "auth": "session",
        "purpose": "Start a Payme/Click checkout for a paid plan; returns a payment_url to redirect the user to.",
    },
    {
        "path": "/api/payments/{id}/",
        "method": "GET",
        "auth": "session",
        "purpose": "Poll a payment status while the user is on the gateway (pending/paid/cancelled).",
    },
    {
        "path": "/webhooks/payme/",
        "method": "POST",
        "auth": "payme-basic",
        "purpose": "Payme Merchant API webhook (CheckPerform/Create/Perform/Cancel/CheckTransaction).",
    },
    {
        "path": "/webhooks/click/",
        "method": "POST",
        "auth": "click-md5-sign",
        "purpose": "Click Shop API webhook: Prepare (action=0) and Complete (action=1).",
    },
    {
        "path": "/api/gamification/badges/",
        "method": "GET",
        "auth": "session",
        "purpose": "All badges with the current user's earned state, plus XP and level.",
    },
    {
        "path": "/api/gamification/badges/check/",
        "method": "POST",
        "auth": "session",
        "purpose": "Re-evaluate and persist badges from current stats.",
    },
]


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    data = {
        "title": "Abiturend Platform API",
        "version": API_VERSION,
        "endpoints": API_ENDPOINTS,
    }
    return Response(data)