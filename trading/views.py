from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from trading.models import (
    Order,
    Stock,
)
from trading.serializers import (
    OrderSerializer,
    StockSerializer,
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
        return self.queryset.filter(user=self.request.user)
