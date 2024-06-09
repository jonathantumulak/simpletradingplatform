from django.utils.translation import gettext_lazy as _


class OrderTypes:
    BUY = 1
    SELL = 2

    CHOICES = (
        (BUY, _("Buy")),
        (SELL, _("Sell")),
    )
