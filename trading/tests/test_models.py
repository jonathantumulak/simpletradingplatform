from django.test import TestCase
from trading.factories import (
    OrderFactory,
    StockFactory,
    UserFactory,
)
from trading.models import Order


class StockTestCase(TestCase):
    def setUp(self):
        self.stock = StockFactory()

    def test_interest_str(self):
        """Testing __str__ method of Stock"""
        self.assertEqual(
            str(self.stock), f"{self.stock.name} ({self.stock.symbol})"
        )


class OrderTestCase(TestCase):
    def setUp(self):
        self.stock = StockFactory()
        self.user = UserFactory()
        self.order = OrderFactory(
            stock=self.stock,
            user=self.user,
            quantity=10,
        )

    def test_manager_get_available_balance(self):
        """Testing get_available_balance method of OrderManager"""
        order2 = OrderFactory(stock=self.stock, user=self.user)
        balance = Order.objects.get_available_balance(
            stock=self.stock, user=self.user
        )
        self.assertEqual(balance, self.order.quantity + order2.quantity)

        OrderFactory(
            stock=self.stock,
            user=self.user,
            quantity=-10,
        )
        # balance should be equal to order2
        balance = Order.objects.get_available_balance(
            stock=self.stock, user=self.user
        )
        self.assertEqual(balance, order2.quantity)
