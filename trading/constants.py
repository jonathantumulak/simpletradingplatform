from django.utils.translation import gettext_lazy as _


class OrderTypes:
    BUY = 1
    SELL = 2

    CHOICES = (
        (BUY, _("Buy")),
        (SELL, _("Sell")),
    )

    CSV_MAP = {
        "BUY": BUY,
        "SELL": SELL,
    }


class TradeDataFileStatuses:
    NEW = 0
    PROCESSING = 1
    PROCESSED = 2
    FAILED = 3

    CHOICES = (
        (NEW, _("NEW")),
        (PROCESSING, _("Processing")),
        (PROCESSED, _("Processed")),
        (FAILED, _("Failed")),
    )
