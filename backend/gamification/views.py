from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import badges_payload, level_info, sync_badges, user_stats


class BadgeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = user_stats(request.user)
        badges = badges_payload(request.user)
        return Response(
            {
                "level": level_info(stats["xp"]),
                "earned_count": len([b for b in badges if b["earned"]]),
                "badges": badges,
            }
        )


class BadgeCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sync_badges(request.user)
        stats = user_stats(request.user)
        return Response(
            {
                "level": level_info(stats["xp"]),
                "badges": badges_payload(request.user),
            }
        )