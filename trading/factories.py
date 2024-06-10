import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory
from trading.models import (
    Order,
    Stock,
    TradeDataFile,
)


class UserFactory(DjangoModelFactory):

    username = factory.Faker("user_name")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    class Meta:
        model = User
        django_get_or_create = ["username"]


class StockFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Stock-{n}")
    symbol = factory.Sequence(lambda n: f"s-{n}")
    price = factory.Faker(
        "pydecimal", left_digits=6, right_digits=2, positive=True
    )

    class Meta:
        model = Stock
        django_get_or_create = ["symbol"]


class OrderFactory(DjangoModelFactory):

    user = factory.SubFactory(UserFactory)
    stock = factory.SubFactory(StockFactory)
    quantity = 10
    order_type = Order.BUY

    class Meta:
        model = Order


class TradeDataFileFactory(DjangoModelFactory):
    uploaded_by_user = factory.SubFactory(UserFactory)

    class Meta:
        model = TradeDataFile
