from django.contrib import admin
from .models import Account, Order, OrderItem, Product

admin.site.register(Account)
admin.site.register(Product)
admin.site.register(Order)
admin.site.register(OrderItem)
