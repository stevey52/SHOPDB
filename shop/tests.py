from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from .models import Product, InventoryMovement

class FIFOTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Oil",
            current_stock=0,
            unit_price=Decimal('50.00'),
            cost_price=Decimal('30.00')
        )

    def test_get_fifo_cost_price_no_movements(self):
        # Should fallback to product base cost price
        cost = self.product.get_fifo_cost_price(5)
        self.assertEqual(cost, Decimal('30.00'))

    def test_get_fifo_cost_price_single_batch(self):
        InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('25.00')
        )
        cost = self.product.get_fifo_cost_price(5)
        self.assertEqual(cost, Decimal('25.00'))

    def test_get_fifo_cost_price_multiple_batches(self):
        InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('20.00'),
            date=timezone.now() - timezone.timedelta(days=2)
        )
        InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('40.00'),
            date=timezone.now() - timezone.timedelta(days=1)
        )
        
        # Taking 15 items: 10 @ 20.00 and 5 @ 40.00
        # Total cost = 400. Avg cost = 400 / 15
        cost = float(self.product.get_fifo_cost_price(15))
        self.assertAlmostEqual(cost, 400.0 / 15.0, places=4)

    def test_get_fifo_cost_price_not_enough_stock(self):
        InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('20.00')
        )
        # Taking 15 items but only 10 in stock
        # Should average the cost of available stock
        cost = self.product.get_fifo_cost_price(15)
        self.assertEqual(cost, Decimal('20.00'))

    def test_deduct_from_batches_exact(self):
        mov1 = InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('20.00'),
            date=timezone.now() - timezone.timedelta(days=2)
        )
        mov2 = InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('40.00'),
            date=timezone.now() - timezone.timedelta(days=1)
        )
        
        deductions = self.product.deduct_from_batches(15)
        
        # Should deduct 10 from mov1 and 5 from mov2
        self.assertEqual(len(deductions), 2)
        self.assertEqual(deductions[0][0], mov1)
        self.assertEqual(deductions[0][1], 10)
        self.assertEqual(deductions[1][0], mov2)
        self.assertEqual(deductions[1][1], 5)
        
        # Verify db state
        mov1.refresh_from_db()
        mov2.refresh_from_db()
        self.assertEqual(mov1.remaining_quantity, 0)
        self.assertEqual(mov2.remaining_quantity, 5)

    def test_deduct_from_batches_more_than_stock(self):
        mov = InventoryMovement.objects.create(
            product=self.product,
            movement_type='IN',
            quantity=10,
            remaining_quantity=10,
            cost_price=Decimal('20.00')
        )
        
        deductions = self.product.deduct_from_batches(15)
        
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0][1], 10)
        
        mov.refresh_from_db()
        self.assertEqual(mov.remaining_quantity, 0)
