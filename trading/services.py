import csv
from collections import defaultdict
from typing import (
    Any,
    Tuple,
)

from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import (
    QuerySet,
    Sum,
)
from django.utils import timezone
from more_itertools import ichunked
from trading.constants import OrderTypes
from trading.models import (
    Order,
    Stock,
    TradeDataFile,
)


class ParserException(Exception):
    pass


class InvalidImportFile(ParserException):
    pass


class EmptyImportFile(ParserException):
    pass


class CSVParser:
    def __init__(self, csv_file: str):
        self.reader = None
        self.csv_file = csv_file
        self.missing_headers = []
        self.headers_indexes_dict = {}
        self.expected_headers = ["User", "Stock", "Quantity", "Order Type"]

    def __iter__(self):
        if self.reader is None:
            self._init_reader()

        return self

    def __next__(self):
        raw_row = next(self.reader)
        return self.parse_row(raw_row)

    def _init_reader(self):
        if not default_storage.exists(self.csv_file):
            raise InvalidImportFile(f"Import file not found: {self.csv_file}")
        self.reader = csv.reader(default_storage.open(self.csv_file, "rt"))
        self.parse_header_index()
        self.check_missing_headers()

    def clean_header(self, header: str):
        header = "_".join(header.split(" ")).lower()
        return header

    def parse_header_index(self):
        try:
            headers = next(self.reader)
        except StopIteration:
            raise EmptyImportFile(f"No headers in `{self.csv_file}`")

        for idx, raw_header in enumerate(headers):
            cleaned_header = self.clean_header(raw_header.strip())
            if cleaned_header:
                self.headers_indexes_dict[cleaned_header] = idx

    def check_missing_headers(self):
        for header in self.expected_headers:
            cleaned_header = self.clean_header(header)
            if self.headers_indexes_dict.get(cleaned_header) is None:
                self.missing_headers.append(header)
                continue

        if self.missing_headers:
            error_message = "Headers are not found in the file: '{}'.".format(
                ", ".join(self.missing_headers)
            )
            raise InvalidImportFile(error_message)

    def parse_row(self, row: list[str]) -> dict:
        row_data = {}
        for header in self.expected_headers:
            cleaned_header = self.clean_header(header)
            idx = self.headers_indexes_dict[cleaned_header]
            if cleaned_header == "quantity":
                row_data[cleaned_header] = int(row[idx].strip())
            else:
                row_data[cleaned_header] = row[idx].strip()

        return row_data


class BaseCache:
    def __init__(
        self, model: Any, lookup_field: str = None, csv_field_header: str = None
    ):
        self.model = model
        self.lookup_field = lookup_field
        self.csv_field_header = csv_field_header
        self._cache = None

    def add_items(self, items: list):
        """Query for items to cache"""
        qs = self.model.objects.filter(**{f"{self.lookup_field}__in": items})
        self.build_cache(qs)

    def build_cache(self, queryset: QuerySet):
        """Build cache dict from queryset"""
        raise NotImplementedError

    def build_cache_for_batch(self, rows: list[dict]):
        """Build cache for the given batch"""
        items = []
        for row_data in rows:
            value = row_data.get(self.csv_field_header)
            if value and value not in self._cache.keys():
                items.append(row_data[self.csv_field_header])
        self.add_items(items)


class PortfolioCache(BaseCache):
    """Cache total quantity available for a user. Used for checking if user
    has available quantity when placing SELL orders
    """

    def __init__(
        self,
        model: Order = Order,
        lookup_field: str = "user_id",
        csv_field_header: str = "user",
    ):
        super().__init__(model, lookup_field, csv_field_header)
        self._cache: defaultdict[int, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def build_cache(self, queryset: QuerySet):
        query = (
            queryset.values("user_id", "stock__symbol")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")
        )
        for values in query:
            self._cache[values["user_id"]][values["stock__symbol"]] = values[
                "total_quantity"
            ]

    def find(
        self, user_id: int, stock_symbol: str, quantity: int
    ) -> Tuple[bool, int]:
        """From given user and stock symbol, get available quantity"""
        if quantity < 0:
            if -quantity > self._cache[user_id][stock_symbol]:
                return False, self._cache[user_id][stock_symbol]
        self._cache[user_id][stock_symbol] += quantity
        return True, self._cache[user_id][stock_symbol]


class UserCache(BaseCache):
    """Cache for existing users"""

    def __init__(
        self,
        model: User = User,
        lookup_field: str = "id",
        csv_field_header: str = "user",
    ):
        super().__init__(model, lookup_field, csv_field_header)
        self._cache: defaultdict[int, User | None] = defaultdict(lambda: None)

    def build_cache(self, queryset: QuerySet):
        for user in queryset:
            self._cache[user.id] = user

    def find(self, user_id: str) -> User:
        return self._cache[int(user_id)]


class StockCache(BaseCache):
    """Cache for existing stocks"""

    def __init__(
        self,
        model: Stock = Stock,
        lookup_field: str = "symbol",
        csv_field_header: str = "stock",
    ):
        super().__init__(model, lookup_field, csv_field_header)
        self._cache: defaultdict[str, Stock | None] = defaultdict(lambda: None)

    def build_cache(self, queryset: QuerySet):
        for stock in queryset:
            self._cache[stock.symbol] = stock

    def find(self, stock_symbol: str) -> Stock:
        return self._cache[stock_symbol]


class TradeDataFileProcessor:
    def __init__(self, trade_data_file: TradeDataFile):
        self.trade_data_file = trade_data_file
        self.parser: CSVParser = CSVParser(
            self.trade_data_file.uploaded_file.path
        )
        self.portfolio_cache: PortfolioCache = PortfolioCache()
        self.user_cache: UserCache = UserCache()
        self.stock_cache: StockCache = StockCache()
        self.batch_size = 500

    def _clean_values(self, values: dict[str, Any]) -> dict[str, Any]:
        cleaned_values = {}

        order_type = values.get("order_type")
        if order_type not in OrderTypes.CSV_MAP.keys():
            raise InvalidImportFile(f"Invalid order type: {order_type}")
        else:
            cleaned_values["order_type"] = OrderTypes.CSV_MAP[order_type]

        user_id = values.get("user")
        user = self.user_cache.find(user_id)
        if not user:
            raise InvalidImportFile(f"User (id={user_id}) not found.")
        else:
            cleaned_values["user"] = user

        stock_symbol = values.get("stock")
        stock = self.stock_cache.find(stock_symbol)
        if not stock:
            raise InvalidImportFile(f"Stock (symbol={stock_symbol}) not found.")
        else:
            cleaned_values["stock"] = stock

        cleaned_values["quantity"] = values.get("quantity")
        if cleaned_values["order_type"] == Order.SELL:
            cleaned_values["quantity"] = -cleaned_values["quantity"]

        return cleaned_values

    def _validate_order(self, values: dict[str, Any]):
        symbol = values["stock"].symbol
        user_id = values["user"].id
        allowed, quantity = self.portfolio_cache.find(
            user_id=user_id,
            stock_symbol=symbol,
            quantity=values["quantity"],
        )
        if not allowed:
            raise InvalidImportFile(
                f"Failed to process order. Not enough stock balance "
                f"for {symbol}. Stock available: {quantity}"
            )

    def _build_caches_for_data_batch(self, rows: list):
        self.portfolio_cache.build_cache_for_batch(rows)
        self.user_cache.build_cache_for_batch(rows)
        self.stock_cache.build_cache_for_batch(rows)

    def process(self):
        self.set_to_processing()
        with transaction.atomic():
            for batch in ichunked(self.parser, self.batch_size):
                rows = [row for row in batch]
                self._build_caches_for_data_batch(rows)
                orders = []
                for values in rows:
                    cleaned_values = self._clean_values(values)
                    self._validate_order(cleaned_values)
                    orders.append(Order(**cleaned_values))

                if len(orders) > 0:
                    Order.objects.bulk_create(orders)
            transaction.on_commit(self.set_to_processed)

    def set_to_processing(self):
        self.trade_data_file.status = TradeDataFile.PROCESSING
        self.trade_data_file.save(update_fields=["status"])

    def set_to_processed(self):
        self.trade_data_file.status = TradeDataFile.PROCESSED
        self.trade_data_file.completed_at = timezone.now()
        self.trade_data_file.save(update_fields=["status", "completed_at"])

    def set_to_failed(self, errors: str):
        self.trade_data_file.status = TradeDataFile.FAILED
        self.trade_data_file.completed_at = timezone.now()
        self.trade_data_file.errors = errors
        self.trade_data_file.save(
            update_fields=["status", "errors", "completed_at"]
        )
