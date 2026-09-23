from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import User


def can_edit_content(user, content):
    """Require a current editor role or the current journalist's authorship."""
    return user.role == User.Role.EDITOR or (
        user.role == User.Role.JOURNALIST and content.author_id == user.pk
    )


class ArticlePermission(BasePermission):
    """Enforce article creation, editing and approval rules by role."""

    def has_permission(self, request, view):
        """Allow the action only when the caller's role permits it."""
        if not request.user.is_authenticated:
            return False
        if view.action == "create":
            return request.user.role == User.Role.JOURNALIST
        if view.action == "approve":
            return request.user.role == User.Role.EDITOR
        if request.method not in SAFE_METHODS:
            return request.user.role in {
                User.Role.EDITOR,
                User.Role.JOURNALIST,
            }
        return True

    def has_object_permission(self, request, view, obj):
        """Check read or mutation access for this content object."""
        if request.method in SAFE_METHODS:
            return (
                obj.approved
                or request.user.role == User.Role.EDITOR
                or obj.author == request.user
            )
        if view.action == "approve":
            return request.user.role == User.Role.EDITOR
        return can_edit_content(request.user, obj)


class NewsletterPermission(BasePermission):
    """Allow staff to create newsletters and edit permitted content."""

    def has_permission(self, request, view):
        """Allow the action only when the caller's role permits it."""
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in {User.Role.JOURNALIST, User.Role.EDITOR}

    def has_object_permission(self, request, view, obj):
        """Check read or mutation access for this content object."""
        if request.method in SAFE_METHODS:
            return True
        return can_edit_content(request.user, obj)
