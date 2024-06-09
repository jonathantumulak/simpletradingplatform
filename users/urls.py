
from rest_framework import routers
from users.views import UserViewSet
from django.urls import (
    include,
    path,
)

router = routers.DefaultRouter()
router.register(r'users', UserViewSet)


urlpatterns = [
    path('', include(router.urls)),
]
