from django.db.models import (
    F,
    QuerySet,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from trading.models import (
    Order,
    Stock,
    TradeDataFile,
)
from trading.serializers import (
    InvestmentSerializer,
    OrderSerializer,
    StockSerializer,
    TradeDataFileSerializer,
)


class StockViewSet(viewsets.ModelViewSet):
    """View set for listing available stocks"""

    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    http_method_names = [
        "get",
    ]


class OrderViewSet(viewsets.ModelViewSet):
    """View set for orders"""

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    http_method_names = [
        "get",
        "post",
    ]

    def get_queryset(self, *args, **kwargs) -> QuerySet:
        return self.queryset.filter(user=self.request.user).select_related(
            "stock"
        )


class TradeDataFileViewSet(viewsets.ModelViewSet):
    """View set for Trade Data Files"""

    queryset = TradeDataFile.objects.all()
    serializer_class = TradeDataFileSerializer
    http_method_names = ["post"]


class InvestmentViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = InvestmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["user", "stock__symbol"]
    http_method_names = ["get"]

    def get_queryset(self):
        return self.queryset.annotate_total_quantity_user_stock().annotate(
            total_value=F("total_quantity") * F("stock__price")
        )
