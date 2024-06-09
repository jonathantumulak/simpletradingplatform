from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.models import User
from rest_framework import (
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.permissions import OwnUserPermission
from users.serializers import (
    UserCreateSerializer,
    UserLoginSerializer,
    UserSerializer,
)


class ListNotAllowedMixin:
    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "GET",
            detail='Method "GET" not allowed without lookup',
        )


class UserViewSet(ListNotAllowedMixin, viewsets.ModelViewSet):
    """Viewset for login, logout, get session, register user"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = []
    http_method_names = ["get", "post", "put"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        elif self.action == "login":
            return UserLoginSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ["retrieve", "update"]:
            return [IsAuthenticated(), OwnUserPermission()]
        return super().get_permissions()

    @action(methods=["POST"], detail=False)
    def login(self, request, format=None):
        serializer = self.get_serializer_class()(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
            if user:
                login(request, user)
                user_serializer = UserSerializer(instance=user)
                return Response(
                    user_serializer.data,
                    status=status.HTTP_200_OK,
                )

        return Response(status=status.HTTP_404_NOT_FOUND)

    @action(methods=["GET"], detail=False)
    def logout(self, request, format=None):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_404_NOT_FOUND)
        logout(request)
        return Response(status=status.HTTP_200_OK)
