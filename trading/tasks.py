import traceback

from celery import shared_task
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
