import pathlib

import mock
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
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
from trading.tasks import (
    fetch_trade_data_csv_file,
    process_trade_data_file,
)
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
        self.assertIn(f"User ({max_id + 1}) not found.", trade_data_file.errors)

    def test_invalid_user_str(self):
        self.add_data(OrderData("INVALID", self.stock.symbol, "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        process_trade_data_file.delay(trade_data_file.id)
        trade_data_file.refresh_from_db()
        self.assertEqual(trade_data_file.status, TradeDataFile.FAILED)
        self.assertIsNotNone(trade_data_file.completed_at)
        self.assertIn("User (INVALID) not found.", trade_data_file.errors)

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

    def test_invalid_quantity(self):
        self.add_data(
            OrderData(self.user.id, self.stock.symbol, "INVALID", "BUY")
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
        self.assertIn("Invalid quantity: INVALID", trade_data_file.errors)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class FetchTradeDataFileTaskTestCase(CSVBuilderMixin, TestCase):
    def setUp(self):
        super().setUp()

        # create separate directory for fetching csv
        self.fetch_csv_dir = self.tmp_media_dir.joinpath("fetch_csv_dir/")
        self.upload_storage_dir = default_storage.path(self.fetch_csv_dir)

        self.upload_dir_settings = override_settings(
            CSV_PARSE_PATH=self.upload_storage_dir
        )
        self.upload_dir_settings.enable()
        self.addCleanup(self.cleanup_upload_dir_settings)

        self.user = UserFactory()
        self.stock = StockFactory()
        self.stock2 = StockFactory()
        self.add_data(OrderData(self.user.id, self.stock.symbol, "10", "BUY"))
        self.add_data(OrderData(self.user.id, self.stock2.symbol, "20", "BUY"))
        self.file_path = self.build_csv_file()

    def cleanup_upload_dir_settings(self):
        self.upload_dir_settings.disable()

    def test_fetch_trade_data_file_task(self):
        fetch_trade_data_csv_file.delay()

        self.assertFalse(pathlib.Path(self.file_path).exists())

        trade_data_files = TradeDataFile.objects.all()
        self.assertEqual(trade_data_files.count(), 1)
        trade_data_file = trade_data_files.get()
        self.assertEqual(trade_data_file.status, TradeDataFile.NEW)
        self.assertIsNone(trade_data_file.completed_at)

    def test_fetch_trade_data_file_task_commit(self):
        with mock.patch("django.db.transaction.on_commit", lambda t: t()):
            fetch_trade_data_csv_file.delay()

        self.assertFalse(pathlib.Path(self.file_path).exists())

        trade_data_files = TradeDataFile.objects.all()
        self.assertEqual(trade_data_files.count(), 1)
        trade_data_file = trade_data_files.get()
        self.assertEqual(trade_data_file.status, TradeDataFile.PROCESSED)
        self.assertIsNotNone(trade_data_file.completed_at)

        orders = Order.objects.filter(user=self.user, order_type=Order.BUY)
        self.assertEqual(orders.count(), 2)
