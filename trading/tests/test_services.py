import os
import shutil
import uuid
from collections import namedtuple
from pathlib import Path

import mock
import tablib
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
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
    Stock,
    TradeDataFile,
)
from trading.services import (
    CSVParser,
    EmptyImportFile,
    InvalidImportFile,
    PortfolioCache,
    StockCache,
    TradeDataFileProcessor,
    UserCache,
)


OrderData = namedtuple("OrderData", ["user", "stock", "quantity", "order_type"])
InvalidOrderData = namedtuple(
    "InvalidOrderData",
    [
        "user",
        "stock",
        "quantity",
    ],
)


class CSVBuilderMixin:
    def setUp(self):
        self.tmp_media_dir = Path("test-media/")
        self.settings_override = override_settings(
            MEDIA_ROOT=self.tmp_media_dir,
        )
        self.settings_override.enable()
        super().setUp()
        self.upload_storage_dir = default_storage.path(self.tmp_media_dir)
        self.addCleanup(self.cleanup_settings)

        self.data_list: list[namedtuple] = []

    def cleanup_settings(self):
        self.settings_override.disable()
        if self.tmp_media_dir.exists():
            shutil.rmtree(self.tmp_media_dir)

    def add_data(self, data: namedtuple):
        self.data_list.append(data)

    def to_csv_headers(self, fields: tuple[str]) -> list[str]:
        return [" ".join(field.strip().split("_")).title() for field in fields]

    def build_csv_file(self) -> str:
        filename, content = self.write_csv()
        return self.save_uploaded_file(filename, content)

    def write_csv(self) -> tuple[str, str | bytes]:
        filename = f"test-{uuid.uuid4()}.csv"
        if self.data_list:
            field_names = self.data_list[0]._fields
            field_labels = self.to_csv_headers(field_names)
            data = [item for item in self.data_list]
            dataset = tablib.Dataset(*data, headers=field_labels)
            content = dataset.export("csv")
        else:
            content = ""

        return filename, content

    def save_uploaded_file(self, filename: str, content: str | bytes) -> str:
        full_path = os.path.join(self.upload_storage_dir, filename)

        dir_path = Path(full_path).parent
        dir_path.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8")
        default_storage.save(full_path, ContentFile(data))

        return full_path


class CSVParserTestCase(CSVBuilderMixin, TestCase):
    def test_csv_parser(self):
        self.add_data(OrderData("1", "NVDA", "10", "BUY"))

        parser = CSVParser(self.build_csv_file())
        rows = [row for row in parser]
        self.assertDictEqual(
            rows[0],
            {"user": 1, "stock": "NVDA", "quantity": 10, "order_type": "BUY"},
        )

    def test_csv_parser_missing_header_error(self):
        self.add_data(InvalidOrderData("1", "NVDA", "10"))

        parser = CSVParser(self.build_csv_file())
        with self.assertRaises(InvalidImportFile):
            parser.__iter__()

    def test_csv_parser_missing_file_error(self):
        parser = CSVParser("invalid_path")
        with self.assertRaises(InvalidImportFile):
            parser.__iter__()

    def test_csv_parser_empty_file_error(self):
        parser = CSVParser(self.build_csv_file())
        with self.assertRaises(EmptyImportFile):
            parser.__iter__()


class UserCacheTestCase(TestCase):
    csv_field = "user"
    instance_factory = UserFactory
    cache_class = UserCache
    model = User
    cache_key_lookup = "id"

    def setUp(self):
        self.instance = self.instance_factory()
        self.cache = self.cache_class()

    def get_invalid_cache_key(self):
        return self.model.objects.aggregate(max=Max("id"))["max"] + 1

    def test_instance_cache(self):
        self.cache.build_cache_for_batch(
            [{self.csv_field: getattr(self.instance, self.cache_key_lookup)}]
        )
        self.assertEqual(
            self.cache.find(getattr(self.instance, self.cache_key_lookup)),
            self.instance,
        )

        invalid = self.get_invalid_cache_key()
        self.assertIsNone(self.cache.find(invalid))


class StockCacheTestCase(UserCacheTestCase):
    csv_field = "stock"
    instance_factory = StockFactory
    cache_class = StockCache
    model = Stock
    cache_key_lookup = "symbol"

    def get_invalid_cache_key(self):
        return "NONE"


class PortfolioCacheTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user2 = UserFactory()
        self.stock = StockFactory()
        self.stock2 = StockFactory()
        self.order = OrderFactory(
            stock=self.stock, user=self.user, quantity=10, order_type=Order.BUY
        )
        self.order2 = OrderFactory(
            stock=self.stock, user=self.user2, quantity=20, order_type=Order.BUY
        )
        self.cache = PortfolioCache()

    def test_cache(self):
        self.cache.build_cache_for_batch(
            [{"user": self.user.id}, {"user": self.user2.id}]
        )
        allowed, quantity = self.cache.find(self.user.id, self.stock.symbol, 15)
        self.assertTrue(allowed)
        self.assertEqual(self.order.quantity + 15, quantity)

        allowed, quantity = self.cache.find(
            self.user2.id, self.stock2.symbol, -30
        )
        self.assertFalse(allowed)
        self.assertEqual(self.order2.quantity, 20)


class TradeDataFileProcessorTestCase(CSVBuilderMixin, TestCase):
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
        processor = TradeDataFileProcessor(self.trade_data_file)
        processor.process()

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
            processor = TradeDataFileProcessor(self.trade_data_file)
            processor.process()

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

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()

    def test_invalid_user(self):
        max_id = User.objects.aggregate(max=Max("id"))["max"]
        self.add_data(OrderData(max_id + 1, self.stock.symbol, "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()

    def test_invalid_user_str(self):
        self.add_data(OrderData("INVALID", self.stock.symbol, "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()

    def test_invalid_stock(self):
        self.add_data(OrderData(self.user.id, "NONE", "10", "BUY"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()

    def test_insufficient_balance(self):
        order = OrderFactory(quantity=10)
        self.add_data(OrderData(self.user.id, order.stock.symbol, "20", "SELL"))
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()

    def test_invalid_quantity(self):
        order = OrderFactory(quantity=10)
        self.add_data(
            OrderData(self.user.id, order.stock.symbol, "INVALID", "BUY")
        )
        filename, content = self.write_csv()
        trade_data_file = TradeDataFileFactory(
            uploaded_by_user=self.user,
            uploaded_file=SimpleUploadedFile(filename, content.encode("utf-8")),
        )

        processor = TradeDataFileProcessor(trade_data_file)
        with self.assertRaises(InvalidImportFile):
            processor.process()
