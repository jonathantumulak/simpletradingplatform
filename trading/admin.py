from django.contrib import admin
from trading.models import (
    Order,
    Stock,
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


admin.site.register(Stock, StockAdmin)
admin.site.register(Order, OrderAdmin)
