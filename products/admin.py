from django.contrib import admin
from .models import Category, Product, OrderItem, Order

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'in_stock', 'created_at']
    list_filter = ['category', 'in_stock', 'created_at']
    search_fields = ['name', 'description', 'category__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

# Register other models normally
admin.site.register(Category)
admin.site.register(OrderItem)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'delivery_location', 'address', 'paid']
    list_filter = ['delivery_location']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
