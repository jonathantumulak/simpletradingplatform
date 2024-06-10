from django.contrib import admin
from trading.models import (
    Order,
    Stock,
    TradeDataFile,
)


class StockAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "price")


class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "stock", "order_type", "quantity")
    search_fields = (
        "user__username",
        "stock__symbol",
    )
    list_filter = ("order_type",)


class TradeDataFileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "completed_at",
    )


admin.site.register(Stock, StockAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(TradeDataFile, TradeDataFileAdmin)
