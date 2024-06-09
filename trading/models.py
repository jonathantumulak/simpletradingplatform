from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from trading.constants import OrderTypes


class Stock(TimeStampedModel):
    name = models.CharField(verbose_name=_("Name"), max_length=255)
    symbol = models.CharField(verbose_name=_("Symbol"), max_length=5)
    price = models.DecimalField(
        verbose_name=_("Price"),
        max_digits=settings.TRANSACTION_MAX_DIGITS,
        decimal_places=settings.TRANSACTION_DECIMAL_PLACES,
        help_text=_("Price in USD"),
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})"


class OrderManager(models.Manager):
    def get_available_balance(self, stock: Stock, user: User) -> int:
        return (
            self.get_queryset()
            .filter(stock=stock, user=user)
            .aggregate(Sum("quantity"))["quantity__sum"]
        )


class Order(OrderTypes, TimeStampedModel):
    user = models.ForeignKey(
        User,
        related_name="orders",
        on_delete=models.CASCADE,
    )
    stock = models.ForeignKey(
        Stock,
        verbose_name=_("Stock"),
        related_name="orders",
        on_delete=models.CASCADE,
    )
    quantity = models.BigIntegerField(
        verbose_name=_("Quantity"),
    )
    order_type = models.PositiveSmallIntegerField(
        verbose_name=_("Order Type"),
        choices=OrderTypes.CHOICES,
    )

    objects = OrderManager()
