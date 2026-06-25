from django.db import models
from django.utils import timezone

class Product(models.Model):
    name = models.CharField(max_length=255)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_fifo_cost_price(self, quantity):
        """
        Calculate FIFO cost price for a given quantity
        Returns the weighted average cost price based on available stock batches
        """
        # Get all stock-in movements with cost prices and remaining stock, ordered by date (FIFO)
        stock_in_movements = self.movements.filter(
            movement_type='IN',
            cost_price__isnull=False,
            remaining_quantity__gt=0  # Only batches with available stock
        ).order_by('date')
        
        if not stock_in_movements:
            return self.cost_price  # Fallback to product's base cost price
        
        total_cost = 0
        remaining_quantity = quantity
        
        for movement in stock_in_movements:
            if remaining_quantity <= 0:
                break
            
            # Calculate how much we can take from this batch
            batch_quantity = min(remaining_quantity, movement.remaining_quantity)
            total_cost += batch_quantity * movement.cost_price
            remaining_quantity -= batch_quantity
        
        if quantity - remaining_quantity > 0:
            return total_cost / (quantity - remaining_quantity)
        
        return self.cost_price  # Fallback if no stock available

    def deduct_from_batches(self, quantity):
        """
        Deduct quantity from available batches using FIFO logic
        Returns list of (batch, quantity_deducted) tuples
        """
        # Get all stock-in movements with remaining stock, ordered by date (FIFO)
        stock_in_movements = self.movements.filter(
            movement_type='IN',
            remaining_quantity__gt=0
        ).order_by('date')
        
        deductions = []
        remaining_quantity = quantity
        
        for movement in stock_in_movements:
            if remaining_quantity <= 0:
                break
            
            # Calculate how much to deduct from this batch
            batch_quantity = min(remaining_quantity, movement.remaining_quantity)
            
            # Update the remaining quantity
            movement.remaining_quantity -= batch_quantity
            movement.save()
            
            deductions.append((movement, batch_quantity))
            remaining_quantity -= batch_quantity
        
        return deductions

class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    sale = models.ForeignKey('Sale', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory_movements')
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory_movements')
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Available quantity left in this batch
    date = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=255, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.movement_type} - {self.product.name} ({self.quantity})"

class Client(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_debt(self):
        # Calculate total debt: Sum of (total_price - amount_paid) for credit sales - sum of payments
        credit_sales = [s for s in self.sales.all() if s.is_credit]
        unpaid_amount = sum(s.total_price - s.amount_paid for s in credit_sales)
        
        credit_invoices = [i for i in getattr(self, 'invoices').all() if i.is_credit] if hasattr(self, 'invoices') else []
        unpaid_amount += sum(i.total_price - i.amount_paid for i in credit_invoices)
        
        payments_total = sum(p.amount for p in self.debt_payments.all())
        return unpaid_amount - payments_total

class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date = models.DateTimeField(default=timezone.now)
    is_credit = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def total_price(self):
        return self.quantity * self.price_at_sale

    @property
    def total_cost(self):
        if self.cost_price:
            return self.quantity * self.cost_price
        return 0

    @property
    def profit(self):
        return self.total_price - self.total_cost

    @property
    def profit_margin(self):
        if self.total_price > 0:
            return (self.profit / self.total_price) * 100
        return 0

    @property
    def balance_due(self):
        if self.is_credit:
            return self.total_price - self.amount_paid
        return 0

    def __str__(self):
        return f"Sale: {self.product.name} x {self.quantity}"

class Invoice(models.Model):
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    date = models.DateTimeField(default=timezone.now)
    is_credit = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(null=True, blank=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_cost(self):
        return sum(item.total_cost for item in self.items.all())

    @property
    def profit(self):
        return self.total_price - self.total_cost

    @property
    def balance_due(self):
        if self.is_credit:
            return self.total_price - self.amount_paid
        return 0

    def __str__(self):
        client_name = self.client.name if self.client else "Walk-in"
        return f"Invoice {self.id} - {client_name}"

class SaleItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    @property
    def total_price(self):
        return self.quantity * self.price_at_sale

    @property
    def total_cost(self):
        if self.cost_price:
            return self.quantity * self.cost_price
        return 0

    @property
    def profit(self):
        return self.total_price - self.total_cost

    @property
    def date(self):
        return self.invoice.date

    @property
    def client(self):
        return self.invoice.client

    @property
    def is_credit(self):
        return self.invoice.is_credit

    @property
    def amount_paid(self):
        return 0

    def __str__(self):
        return f"Item: {self.product.name} x {self.quantity}"

class DebtPayment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='debt_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Payment: {self.client.name} - {self.amount}"

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
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name='journal_entries')
    debt_payment = models.ForeignKey(DebtPayment, on_delete=models.CASCADE, null=True, blank=True, related_name='journal_entries')

    def __str__(self):
        return f"{self.entry_type}: {self.amount}"
