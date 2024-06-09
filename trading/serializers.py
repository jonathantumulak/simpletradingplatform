from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from trading.models import (
    Order,
    Stock,
)


class StockSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        normalize_output=True,
        max_digits=settings.TRANSACTION_MAX_DIGITS,
        decimal_places=settings.TRANSACTION_DECIMAL_PLACES,
    )

    class Meta:
        model = Stock
        fields = ["id", "name", "symbol", "price"]


class OrderSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Order
        fields = [
            "id",
            "stock",
            "quantity",
            "order_type",
            "user",
        ]

    def create(self, validated_data: dict) -> Order:
        order_type = validated_data.get("order_type")
        if order_type == Order.SELL:
            available_quantity = Order.objects.get_available_balance(
                stock=validated_data["stock"],
                user=validated_data["user"],
            )
            if available_quantity < validated_data["quantity"]:
                raise serializers.ValidationError(
                    _("Not enough stock balance. Stock available: {}").format(
                        available_quantity
                    )
                )
            validated_data["quantity"] = -validated_data["quantity"]
        return super().create(validated_data)
