import mock
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Max
from django.test import (
    TestCase,
    override_settings,
)
from trading.factories import (
    OrderFactory,
    StockFactory,
    TradeDataFileFactory,
    UserFactory,
)
from trading.models import (
    Order,
    TradeDataFile,
)
from trading.tasks import process_trade_data_file
from trading.tests.test_services import (
    CSVBuilderMixin,
    OrderData,
)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ProcessTradeDataFileTaskTestCase(CSVBuilderMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.stock = StockFactory()
        self.add_data(OrderData(self.user.id, self.stock.symbol, "10", "BUY"))

        filename, content = self.write_csv()
        self.trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

    def test_process_file(self):
        process_trade_data_file.delay(self.trade_data_file.id)

        self.trade_data_file.refresh_from_db()
        self.assertEqual(self.trade_data_file.status, TradeDataFile.PROCESSING)

        self.assertTrue(
            Order.objects.filter(
                user=self.user,
                stock=self.stock,
                quantity=10,
                order_type=Order.BUY,
            ).exists()
        )

    def test_process_file_commit(self):
        with mock.patch("django.db.transaction.on_commit", lambda t: t()):
            process_trade_data_file.delay(self.trade_data_file.id)

        self.trade_data_file.refresh_from_db()
        self.assertEqual(self.trade_data_file.status, TradeDataFile.PROCESSED)
        self.assertIsNotNone(self.trade_data_file.completed_at)
        self.assertTrue(
            Order.objects.filter(
                user=self.user,
                stock=self.stock,
                quantity=10,
                order_type=Order.BUY,
            ).exists()
        )

    def test_invalid_order_type(self):
        self.add_data(
            OrderData(self.user.id, self.stock.symbol, "10", "INVALID")
        )
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        process_trade_data_file.delay(trade_data_file.id)

        trade_data_file.refresh_from_db()
        self.assertEqual(trade_data_file.status, TradeDataFile.FAILED)
        self.assertIsNotNone(trade_data_file.completed_at)
        self.assertIn("Invalid order type: INVALID", trade_data_file.errors)

    def test_invalid_user(self):
        max_id = User.objects.aggregate(max=Max("id"))["max"]
        self.add_data(OrderData(max_id + 1, self.stock.symbol, "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        process_trade_data_file.delay(trade_data_file.id)
        trade_data_file.refresh_from_db()
        self.assertEqual(trade_data_file.status, TradeDataFile.FAILED)
        self.assertIsNotNone(trade_data_file.completed_at)
        self.assertIn(
            f"User (id={max_id + 1}) not found.", trade_data_file.errors
        )

    def test_invalid_stock(self):
        self.add_data(OrderData(self.user.id, "NONE", "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        process_trade_data_file.delay(trade_data_file.id)
        trade_data_file.refresh_from_db()
        self.assertEqual(trade_data_file.status, TradeDataFile.FAILED)
        self.assertIsNotNone(trade_data_file.completed_at)
        self.assertIn("Stock (symbol=NONE) not found.", trade_data_file.errors)

    def test_insufficient_balance(self):
        order = OrderFactory(user=self.user, quantity=10)
        symbol = order.stock.symbol
        self.add_data(OrderData(self.user.id, symbol, "20", "SELL"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        process_trade_data_file.delay(trade_data_file.id)
        trade_data_file.refresh_from_db()
        self.assertEqual(trade_data_file.status, TradeDataFile.FAILED)
        self.assertIsNotNone(trade_data_file.completed_at)
        self.assertIn(
            f"Failed to process order. Not enough stock balance for {symbol}. Stock available: {order.quantity}",
            trade_data_file.errors,
        )
