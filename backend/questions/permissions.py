from rest_framework.permissions import BasePermission

MANAGE_ROLES = ("teacher", "admin")


class CanManageQuestions(BasePermission):
    """Teacher or admin/board operator can author and manage questions.

    Two tiers are enforced. ``has_permission`` gates the whole role: only a
    teacher or admin may reach write actions at all. ``has_object_permission``
    gates individual rows: a teacher may edit their own questions, while an
    admin/staff member may moderate any question in the bank. Without the
    object tier any teacher could rewrite or delete another teacher's questions.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or (getattr(user, "role", None) in MANAGE_ROLES)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Staff and the admin role moderate the entire bank.
        if user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin":
            return True
        # Teachers are confined to the rows they authored. ``created_by`` is
        # nullable (imported questions have no author), so such rows are
        # admin-only rather than editable by every teacher.
        return obj.created_by_id == user.pk