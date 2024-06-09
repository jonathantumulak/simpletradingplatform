from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from trading.factories import (
    OrderFactory,
    StockFactory,
    UserFactory,
)
from trading.models import Order


class TestStockViewSet(APITestCase):
    def setUp(self):
        self.stock = StockFactory()
        self.url = reverse("stock-list")

    def test_list_stock(self):
        """
        Test listing all stocks
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.stock.id)
        self.assertEqual(data[0]["name"], self.stock.name)
        self.assertEqual(data[0]["symbol"], self.stock.symbol)
        self.assertEqual(data[0]["price"], str(self.stock.price.normalize()))


class TestOrderViewSet(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.stock = StockFactory()
        self.order = OrderFactory(user=self.user, stock=self.stock)
        self.url = reverse("order-list")

    def test_get_list_order(self):
        """
        Test for listing all orders for user
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.order.id)
        self.assertEqual(data[0]["quantity"], self.order.quantity)
        self.assertEqual(data[0]["order_type"], self.order.order_type)
        self.assertEqual(data[0]["stock"], self.order.stock.id)

    def test_get_list_order_not_owned_by_user(self):
        """
        Test for listing all orders for user
        """
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 0)

    def test_get_list_order_non_loggedin_user(self):
        """
        Test for listing all orders for non loggedin user
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_buy_order(self):
        """
        Test for create buy order
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {"stock": self.stock.id, "quantity": 10, "order_type": Order.BUY},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["quantity"], 10)
        self.assertEqual(data["order_type"], Order.BUY)
        self.assertEqual(data["stock"], self.stock.id)

    def test_create_sell_order(self):
        """
        Test for create sell order
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {"stock": self.stock.id, "quantity": 10, "order_type": Order.SELL},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["quantity"], -10)
        self.assertEqual(data["order_type"], Order.SELL)
        self.assertEqual(data["stock"], self.stock.id)

    def test_create_sell_order_not_enough_balance(self):
        """
        Test for create order
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {"stock": self.stock.id, "quantity": 20, "order_type": Order.SELL},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.json()
        self.assertIn(
            "Not enough stock balance. Stock available: {}".format(
                self.order.quantity
            ),
            errors,
        )
