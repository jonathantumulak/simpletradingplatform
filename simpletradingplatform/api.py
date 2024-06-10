from rest_framework import routers
from trading.views import (
    OrderViewSet,
    StockViewSet,
    TradeDataFileViewSet,
)
from users.views import UserViewSet


# Settings
router = routers.DefaultRouter()
router.trailing_slash = "/?"

router.register(r"users", UserViewSet)
router.register(r"stock", StockViewSet)
router.register(r"orders", OrderViewSet)
router.register(r"trade-data-file", TradeDataFileViewSet)
