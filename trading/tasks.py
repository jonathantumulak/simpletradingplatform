import pathlib
import traceback

from celery import (
    chain,
    shared_task,
)
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from trading.models import TradeDataFile
from trading.services import TradeDataFileProcessor


@shared_task
def process_trade_data_file(trade_data_file_pk: int):
    trade_data_file = TradeDataFile.objects.get(pk=trade_data_file_pk)
    processor = TradeDataFileProcessor(trade_data_file)

    try:
        processor.process()
    except Exception as e:
        # catch all exceptions so we can mark as failed
        traceback.print_exc()
        processor.set_to_failed(str(e))


@shared_task
def fetch_trade_data_csv_file():
    files = [
        f
        for f in pathlib.Path(settings.CSV_PARSE_PATH).iterdir()
        if f.is_file()
    ]

    processed_files: list[pathlib.Path] = []
    trade_data_files: list[TradeDataFile] = []
    for file in files:
        if file.suffix == ".csv":
            processed_files.append(file)
            with file.open("rb") as f:
                trade_data_files.append(
                    TradeDataFile(
                        uploaded_file=SimpleUploadedFile(file.name, f.read())
                    )
                )

    with transaction.atomic():
        trade_data_files = TradeDataFile.objects.bulk_create(trade_data_files)

    transaction.on_commit(
        lambda: chain(
            *[
                process_trade_data_file.si(trade_data_file.pk)
                for trade_data_file in trade_data_files
            ]
        ).apply_async()
    )

    for file in processed_files:
        file.unlink()
