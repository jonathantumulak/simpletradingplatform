from decimal import Decimal

import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from trading.factories import (
    OrderFactory,
    StockFactory,
    UserFactory,
)
from trading.models import (
    Order,
    Stock,
    TradeDataFile,
)
from trading.tests.test_services import (
    CSVBuilderMixin,
    OrderData,
)


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

    def test_create_buy_order_invalid_quantity(self):
        """
        Test for create buy order with invalid quantity
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {
                "stock": self.stock.id,
                "quantity": "ABC",
                "order_type": Order.BUY,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_buy_order_invalid_order_type(self):
        """
        Test for create buy order with invalid order_type
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            self.url,
            {"stock": self.stock.id, "quantity": 10, "order_type": "INVALID"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TestTradeDataFileViewSet(CSVBuilderMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.stock = StockFactory()
        self.add_data(OrderData(self.user.id, self.stock.symbol, "10", "BUY"))
        self.url = reverse("tradedatafile-list")
        self.client.force_authenticate(user=self.user)

    def test_get_list(self):
        """
        Test for listing all trade data files
        """
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_post(self):
        filename, content = self.write_csv()

        response = self.client.post(
            self.url,
            {
                "uploaded_file": SimpleUploadedFile(
                    filename, content.encode("utf-8")
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()
        trade_data_file = TradeDataFile.objects.get()
        self.assertEqual(data["id"], trade_data_file.id)
        self.assertEqual(trade_data_file.status, TradeDataFile.NEW)
        self.assertEqual(trade_data_file.uploaded_by_user, self.user)

    def test_post_commit(self):
        filename, content = self.write_csv()

        with mock.patch("django.db.transaction.on_commit", lambda t: t()):
            response = self.client.post(
                self.url,
                {
                    "uploaded_file": SimpleUploadedFile(
                        filename, content.encode("utf-8")
                    )
                },
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()
        trade_data_file = TradeDataFile.objects.get()
        self.assertEqual(data["id"], trade_data_file.id)
        self.assertEqual(trade_data_file.status, TradeDataFile.PROCESSED)
        self.assertEqual(trade_data_file.uploaded_by_user, self.user)

    def test_post_unathenticated_user(self):
        self.client.logout()
        filename, content = self.write_csv()

        response = self.client.post(
            self.url,
            {
                "uploaded_file": SimpleUploadedFile(
                    filename, content.encode("utf-8")
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.json()
        trade_data_file = TradeDataFile.objects.get()
        self.assertEqual(data["id"], trade_data_file.id)
        self.assertEqual(trade_data_file.status, TradeDataFile.NEW)
        self.assertIsNone(trade_data_file.uploaded_by_user)


class TestInvestmentViewSet(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.stock = StockFactory()
        self.stock2 = StockFactory(price=Decimal(9367000))
        self.order = OrderFactory(user=self.user, stock=self.stock)
        self.order2 = OrderFactory(user=self.user, stock=self.stock)
        self.order3 = OrderFactory(user=self.user, stock=self.stock2)
        self.user2 = UserFactory()
        self.order4 = OrderFactory(user=self.user2, stock=self.stock)
        self.order5 = OrderFactory(user=self.user2, stock=self.stock2)
        self.order6 = OrderFactory(user=self.user2, stock=self.stock2)
        self.url = reverse("investment-list")

    def assert_total_value(self, response_data: dict):
        for item in response_data:
            stock = Stock.objects.get(symbol=item["stock_symbol"])
            orders = Order.objects.filter(user_id=item["user_id"], stock=stock)
            total_quantity = 0
            for order in orders:
                total_quantity += order.quantity
            expected_total_value = total_quantity * stock.price
            self.assertEqual(
                item["total_value"],
                "{:f}".format(expected_total_value.normalize()),
            )

    def test_get_list(self):
        """
        Test for getting total value of orders for all users
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 4)
        self.assert_total_value(data)

    def test_filter_user(self):
        """
        Test for getting total value of orders of all stocks for a user
        """
        response = self.client.get(self.url, {"user": self.user.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assert_total_value(data)

    def test_filter_stock(self):
        """
        Test for getting total value of orders for all users with a specific stock
        """
        response = self.client.get(
            self.url, {"stock__symbol": self.stock2.symbol}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assert_total_value(data)

    def test_filter_user_and_stock(self):
        response = self.client.get(
            self.url, {"user": self.user.id, "stock__symbol": self.stock.symbol}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assert_total_value(data)
