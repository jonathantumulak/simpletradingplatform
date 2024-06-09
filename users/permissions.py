from rest_framework import permissions


class OwnUserPermission(permissions.BasePermission):
    message = "Not allowed to access other users"

    def has_object_permission(self, request, view, obj):
        # Instance must be request user.
        return obj == request.user
