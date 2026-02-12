from django.db import models
from django.utils import timezone

class Product(models.Model):
    name = models.CharField(max_length=255)
    current_stock = models.IntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.name

class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    sale = models.ForeignKey('Sale', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory_movements')
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    date = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.movement_type} - {self.product.name} ({self.quantity})"

class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity = models.IntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)

    @property
    def total_price(self):
        return self.quantity * self.price_at_sale

    def __str__(self):
        return f"Sale: {self.product.name} x {self.quantity}"

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class MoneyJournal(models.Model):
    JOURNAL_TYPES = [
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    ]
    entry_type = models.CharField(max_length=10, choices=JOURNAL_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='journal_entries')

    def __str__(self):
        return f"{self.entry_type}: {self.amount}"
