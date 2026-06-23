from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, F, Q, Prefetch
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Product, InventoryMovement, Sale, MoneyJournal, ExpenseCategory, Client, DebtPayment, Invoice, SaleItem
from .forms import SaleForm, MovementForm, MoneyJournalForm, ClientForm, DebtPaymentForm
from .mixins import ManagerRequiredMixin, DateFilterMixin

class MyLogoutView(auth_views.LogoutView):
    def get(self, request, *args, **kwargs):
        """Allow GET requests for logout (to prevent 405 error on browser refresh/back)."""
        return self.post(request, *args, **kwargs)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'shop/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_products'] = Product.objects.count()
        context['low_stock'] = Product.objects.filter(current_stock__lt=5).count()
        context['total_income'] = float(MoneyJournal.objects.filter(entry_type='Income').aggregate(Sum('amount'))['amount__sum'] or 0)
        context['total_expense'] = float(MoneyJournal.objects.filter(entry_type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0)
        context['balance'] = round(context['total_income'] - context['total_expense'], 2)
        
        # Debt Stats
        total_owed = sum(c.total_debt for c in Client.objects.all())
        context['total_debt'] = float(total_owed)
        
        # Calculate last 7 days data
        days = []
        sales_data = []
        profit_data = []
        expenses_data = []
        
        for i in range(6, -1, -1):
            date = timezone.now().date() - timezone.timedelta(days=i)
            days.append(date.strftime('%b %d'))
            
            # Daily Sales (Total Volume - Accrual)
            daily_sales = Sale.objects.filter(date__date=date).aggregate(
                total=Sum(F('quantity') * F('price_at_sale'))
            )['total'] or 0
            
            daily_invoice_sales = SaleItem.objects.filter(invoice__date__date=date).aggregate(
                total=Sum(F('quantity') * F('price_at_sale'))
            )['total'] or 0
            
            daily_sales_total = float(daily_sales) + float(daily_invoice_sales)
            sales_data.append(daily_sales_total)
            
            # Daily COGS - use actual sale cost_price (FIFO) instead of current product cost_price
            daily_cogs = 0
            daily_sales_queryset = Sale.objects.filter(date__date=date).select_related('product')
            for sale in daily_sales_queryset:
                if sale.cost_price:
                    daily_cogs += sale.cost_price
                else:
                    # Fallback to current product cost_price if sale cost_price is null
                    daily_cogs += sale.quantity * sale.product.cost_price
                    
            daily_invoice_sales_queryset = SaleItem.objects.filter(invoice__date__date=date).select_related('product')
            for item in daily_invoice_sales_queryset:
                if item.cost_price:
                    daily_cogs += item.cost_price
                else:
                    daily_cogs += item.quantity * item.product.cost_price
            
            # Manual Expenses for the day
            daily_expenses = MoneyJournal.objects.filter(entry_type='Expense', date__date=date).aggregate(
                total=Sum('amount')
            )['total'] or 0
            expenses_data.append(float(daily_expenses))
            
            # Profit = Total Sales Value - COGS - Expenses (Accrual)
            # This ensures that credit sales don't look like losses because of COGS.
            daily_profit = daily_sales_total - float(daily_cogs) - float(daily_expenses)
            profit_data.append(round(daily_profit, 2))

        context['chart_labels'] = days
        context['chart_sales'] = sales_data
        context['chart_profit'] = profit_data
        context['chart_expenses'] = expenses_data
        return context

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'shop/product_list.html'
    context_object_name = 'products'
    paginate_by = 10
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    fields = ['name', 'current_stock', 'unit_price', 'cost_price']
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('product_list')

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    fields = ['name', 'current_stock', 'unit_price', 'cost_price']
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('product_list')


class ProductDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'shop/product_confirm_delete.html'
    success_url = reverse_lazy('product_list')

class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'shop/client_list.html'
    context_object_name = 'clients'
    paginate_by = 10
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('sales', 'debt_payments')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

class ClientDetailView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'shop/client_detail.html'
    context_object_name = 'sales'
    paginate_by = 10

    def get_queryset(self):
        self.client = get_object_or_404(Client, pk=self.kwargs['pk'])
        return Sale.objects.filter(client=self.client).order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.client
        context['payments'] = DebtPayment.objects.filter(client=self.client).order_by('-date')
        context['invoices'] = Invoice.objects.filter(client=self.client).order_by('-date')
        return context

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'shop/client_form.html'
    success_url = reverse_lazy('client_list')

class InventoryHistoryView(LoginRequiredMixin, DateFilterMixin, ListView):
    model = InventoryMovement
    template_name = 'shop/inventory_history.html'
    context_object_name = 'movements'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('product', 'sale')
        queryset = self.apply_date_filters(queryset)
            
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query) | 
                Q(reference__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context

class SalesHistoryView(LoginRequiredMixin, DateFilterMixin, ListView):
    model = Sale
    template_name = 'shop/sales_history.html'
    context_object_name = 'sales'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('product', 'client')
        queryset = self.apply_date_filters(queryset)
            
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query) |
                Q(client__name__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context

class MoneyJournalView(ManagerRequiredMixin, LoginRequiredMixin, DateFilterMixin, ListView):
    model = MoneyJournal
    template_name = 'shop/money_journal.html'
    context_object_name = 'entries'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_date_filters(queryset)
            
        category_id = self.request.GET.get('category')
        if category_id:
             queryset = queryset.filter(category_id=category_id)

        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(description__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['categories'] = ExpenseCategory.objects.all()
        context['selected_category'] = self.request.GET.get('category', '')
        return context

class LowStockView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'shop/product_list.html'
    context_object_name = 'products'
    ordering = ['name']
    
    def get_queryset(self):
        return Product.objects.filter(current_stock__lt=5)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header_title'] = 'Low Stock Alert'
        return context

class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'shop/sale_form.html'
    success_url = reverse_lazy('sales_history')

    @transaction.atomic
    def form_valid(self, form):
        sale = form.save()
        
        # Calculate FIFO cost price for this sale
        fifo_cost_price = sale.product.get_fifo_cost_price(sale.quantity)
        sale.cost_price = fifo_cost_price
        sale.save()
        
        # 1. Update Product Stock
        product = sale.product
        product.current_stock -= sale.quantity
        product.save()

        # 2. Deduct from inventory batches using FIFO
        deductions = product.deduct_from_batches(sale.quantity)
        
        # 3. Record Inventory Movement (OUT) with cost price and remaining_quantity=0
        InventoryMovement.objects.create(
            product=product,
            sale=sale,
            movement_type='OUT',
            quantity=sale.quantity,
            remaining_quantity=0,  # OUT movements have no remaining stock
            date=sale.date,
            reference=f'Sale ID: {sale.id}',
            cost_price=fifo_cost_price
        )

        # 4. Record Money Journal Entry (Income)
        # For credit sales, we only record the upfront payment as income.
        amount_to_record = sale.total_price if not sale.is_credit else sale.amount_paid
        
        if amount_to_record > 0:
            description = f'Sale of {product.name} (x{sale.quantity})'
            if sale.is_credit:
                description += f' - Partial Payment from {sale.client.name}'
            
            MoneyJournal.objects.create(
                entry_type='Income',
                amount=amount_to_record,
                description=description,
                date=sale.date,
                sale=sale
            )
        return super().form_valid(form)

class SaleDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Sale
    template_name = 'shop/sale_confirm_delete.html'
    success_url = reverse_lazy('sales_history')

    @transaction.atomic
    def form_valid(self, form):
        sale = self.get_object()
        product = sale.product
        
        # 1. Restore Product Stock
        product.current_stock += sale.quantity
        product.save()

        # 2. Cleanup records
        if hasattr(sale, 'inventory_movements'):
             sale.inventory_movements.all().delete()
        if hasattr(sale, 'journal_entries'):
             sale.journal_entries.all().delete()
        
        # Fix legacy references (orphan entries not explicitly linked)
        InventoryMovement.objects.filter(reference=f'Sale ID: {sale.id}').delete()
        from datetime import timedelta
        # Expanded window to 1 hour to be robust against manual entry/lag
        time_window = timedelta(hours=1)
        
        # Search for unlinked Income entries matching this sale's product and quantity
        MoneyJournal.objects.filter(
            Q(sale__isnull=True),
            Q(entry_type='Income'),
            Q(description__icontains=f'Sale of {product.name} (x{sale.quantity})'),
            Q(amount__in=[sale.total_price, sale.amount_paid]),
            Q(date__range=(sale.date - time_window, sale.date + time_window))
        ).delete()

        # Clean up any "Reversal" expenses that might have been created by old logic
        MoneyJournal.objects.filter(
            entry_type='Expense',
            description__icontains=f'Reversal: Deleted Sale of {product.name}',
        ).delete()
             
        messages.success(self.request, f"Sale of {product.name} deleted. Stock restored and records cleared.")
        return super().form_valid(form)

class DebtPaymentCreateView(LoginRequiredMixin, CreateView):
    model = DebtPayment
    form_class = DebtPaymentForm
    template_name = 'shop/debt_payment_form.html'
    
    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.client.pk})

    def get_initial(self):
        initial = super().get_initial()
        client_id = self.request.GET.get('client')
        if client_id:
            initial['client'] = client_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client_id = self.request.GET.get('client')
        if client_id:
            try:
                context['client'] = Client.objects.get(pk=client_id)
            except Client.DoesNotExist:
                pass
        return context

    @transaction.atomic
    def form_valid(self, form):
        payment = form.save()
        # Record Income in Money Journal
        MoneyJournal.objects.create(
            entry_type='Income',
            amount=payment.amount,
            description=f'Debt Payment from {payment.client.name}',
            date=payment.date,
            debt_payment=payment
        )
        messages.success(self.request, f"Payment of {payment.amount} recorded for {payment.client.name}.")
        return super().form_valid(form)

class DebtPaymentDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = DebtPayment
    template_name = 'shop/debt_payment_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.client.pk})

    @transaction.atomic
    def form_valid(self, form):
        payment = self.get_object()
        # Remove corresponding entry in Money Journal
        MoneyJournal.objects.filter(debt_payment=payment).delete()
        messages.success(self.request, f"Payment of {payment.amount} removed. Client balance updated.")
        return super().form_valid(form)

class SaleUpdateView(ManagerRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Sale
    form_class = SaleForm
    template_name = 'shop/sale_form.html'
    success_url = reverse_lazy('sales_history')

    @transaction.atomic
    def form_valid(self, form):
        old_sale = Sale.objects.get(pk=self.object.pk)
        old_quantity = old_sale.quantity
        old_product = old_sale.product
        
        sale = form.save()
        
        # 1. Handle stock changes if product or quantity changed
        if old_product != sale.product:
            old_product.current_stock += old_quantity
            old_product.save()
            sale.product.current_stock -= sale.quantity
            sale.product.save()
        elif old_quantity != sale.quantity:
            sale.product.current_stock += (old_quantity - sale.quantity)
            sale.product.save()

        # 2. Update/Sync Money Journal and Inventory Movement Dates
        MoneyJournal.objects.filter(sale=sale).delete()
        InventoryMovement.objects.filter(sale=sale).update(date=sale.date)
        
        amount_to_record = sale.total_price if not sale.is_credit else sale.amount_paid
        if amount_to_record > 0:
            description = f'Sale of {sale.product.name} (x{sale.quantity})'
            if sale.is_credit:
                description += f' - Partial Payment from {sale.client.name}'
            
            MoneyJournal.objects.create(
                entry_type='Income',
                amount=amount_to_record,
                description=description,
                date=sale.date,
                sale=sale
            )
            
        messages.success(self.request, f"Sale updated successfully.")
        return super().form_valid(form)

class BulkRestockView(ManagerRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = 'shop/bulk_restock.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all().order_by('name')
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        product_ids = request.POST.getlist('product_ids')
        reference = request.POST.get('reference', 'Bulk Restock')
        date_str = request.POST.get('date')
        
        # Determine the date for movements
        if date_str:
            movement_date = timezone.datetime.strptime(date_str, '%Y-%m-%d')
            movement_date = timezone.make_aware(movement_date)
        else:
            movement_date = timezone.now()

        updated_count = 0
        for pid in product_ids:
            qty_added = request.POST.get(f'qty_{pid}')
            cost_price = request.POST.get(f'cost_price_{pid}')
            
            if qty_added and int(qty_added) > 0:
                qty = int(qty_added)
                product = Product.objects.get(pk=pid)
                
                # Convert cost price to decimal if provided
                cost_price_decimal = None
                if cost_price and cost_price.strip():
                    try:
                        cost_price_decimal = float(cost_price)
                    except ValueError:
                        pass
                
                # 1. Update stock
                product.current_stock += qty
                
                # Update product cost price if this is the first stock or if provided
                if cost_price_decimal and (not product.cost_price or request.POST.get(f'update_cost_{pid}') == 'on'):
                    product.cost_price = cost_price_decimal
                
                product.save()
                
                # 2. Record movement with cost price and remaining quantity
                movement = InventoryMovement.objects.create(
                    product=product,
                    movement_type='IN',
                    quantity=qty,
                    remaining_quantity=qty,  # All stock is available initially
                    date=movement_date,
                    reference=reference,
                    cost_price=cost_price_decimal
                )
                updated_count += 1
        
        if updated_count > 0:
            messages.success(request, f"Successfully restocked {updated_count} products.")
        else:
            messages.warning(request, "No stock updates performed.")
            
        return redirect('inventory_history')

class MovementCreateView(LoginRequiredMixin, CreateView):
    model = InventoryMovement
    form_class = MovementForm
    template_name = 'shop/movement_form.html'
    success_url = reverse_lazy('inventory_history')

    def get_initial(self):
        initial = super().get_initial()
        initial['date'] = timezone.now().date()
        return initial

    @transaction.atomic
    def form_valid(self, form):
        movement = form.save()
        
        # Set remaining_quantity based on movement type
        if movement.movement_type == 'IN':
            movement.remaining_quantity = movement.quantity  # All stock is available
            # Update Product Stock
            product = movement.product
            product.current_stock += movement.quantity
            product.save()
        else:
            movement.remaining_quantity = 0  # OUT movements have no remaining stock
            # For OUT movements, deduct from available batches
            if movement.product.current_stock >= movement.quantity:
                movement.product.deduct_from_batches(movement.quantity)
                movement.product.current_stock -= movement.quantity
                movement.product.save()
        
        movement.save()
        return super().form_valid(form)

class MovementUpdateView(LoginRequiredMixin, UpdateView):
    model = InventoryMovement
    form_class = MovementForm
    template_name = 'shop/movement_form.html'
    success_url = reverse_lazy('inventory_history')

    @transaction.atomic
    def form_valid(self, form):
        # Get the original movement to reverse its stock effect
        original_movement = InventoryMovement.objects.get(pk=self.object.pk)
        product = original_movement.product
        
        # Reverse the original movement's effect on stock
        if original_movement.movement_type == 'IN':
            product.current_stock -= original_movement.quantity
        else:
            product.current_stock += original_movement.quantity
        
        # Save the updated movement
        movement = form.save()
        
        # Apply the new movement's effect on stock
        if movement.movement_type == 'IN':
            product.current_stock += movement.quantity
        else:
            product.current_stock -= movement.quantity
            
        product.save()
        return super().form_valid(form)

class ExpenseCategoryListView(ManagerRequiredMixin, LoginRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'shop/category_list.html'
    context_object_name = 'categories'
    ordering = ['name']

class ExpenseCategoryCreateView(ManagerRequiredMixin, LoginRequiredMixin, CreateView):
    model = ExpenseCategory
    fields = ['name']
    template_name = 'shop/category_form.html'
    success_url = reverse_lazy('category_list')

class MoneyJournalCreateView(ManagerRequiredMixin, LoginRequiredMixin, CreateView):
    model = MoneyJournal
    form_class = MoneyJournalForm
    template_name = 'shop/journal_form.html'
    success_url = reverse_lazy('money_journal')

    def get_initial(self):
        initial = super().get_initial()
        initial['date'] = timezone.now().date()
        return initial

class ProfitReportView(ManagerRequiredMixin, LoginRequiredMixin, ListView):
    model = Product
    template_name = 'shop/profit_report.html'
    ordering = ['name']
    paginate_by = 20
    
    def get_queryset(self):
        # Get date filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Filter sales by date range if provided
        sales_filter = Sale.objects.all()
        items_filter = SaleItem.objects.all()
        if start_date:
            try:
                start_dt = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                start_dt = timezone.make_aware(start_dt)
                sales_filter = sales_filter.filter(date__gte=start_dt)
                items_filter = items_filter.filter(invoice__date__gte=start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = timezone.make_aware(end_dt.replace(hour=23, minute=59, second=59))
                sales_filter = sales_filter.filter(date__lte=end_dt)
                items_filter = items_filter.filter(invoice__date__lte=end_dt)
            except ValueError:
                pass
        
        # Start with all products
        queryset = Product.objects.prefetch_related(
            Prefetch('sales', queryset=sales_filter, to_attr='filtered_sales'),
            Prefetch('saleitem_set', queryset=items_filter, to_attr='filtered_invoice_items')
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        products_data = []
        total_revenue_sum = 0
        total_profit_sum = 0

        # Process each product to calculate profit based on actual sale cost prices
        for product in context['object_list']:
            # Get filtered sales for this product (prefetched)
            sales = product.filtered_sales
            invoice_items = product.filtered_invoice_items
            
            total_sold = sum(sale.quantity for sale in sales) + sum(item.quantity for item in invoice_items)
            
            if total_sold == 0:
                continue
                
            total_revenue = sum(sale.total_price for sale in sales) + sum(item.total_price for item in invoice_items)
            total_cost = sum(sale.total_cost for sale in sales) + sum(item.total_cost for item in invoice_items)
            net_profit = sum(sale.profit for sale in sales if hasattr(sale, 'profit') and sale.profit) + sum(item.profit for item in invoice_items if hasattr(item, 'profit') and item.profit)
            
            if total_revenue > 0:
                margin = (net_profit / total_revenue) * 100
            else:
                margin = 0
            
            products_data.append({
                'name': product.name,
                'total_sold': total_sold,
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'net_profit': net_profit,
                'margin': round(margin, 1)
            })
            
            total_revenue_sum += total_revenue
            total_profit_sum += net_profit
            
        # Sort by Net Profit descending
        products_data.sort(key=lambda x: x['net_profit'], reverse=True)
        
        context['report_data'] = products_data
        context['total_revenue_sum'] = total_revenue_sum
        context['total_profit_sum'] = total_profit_sum
        context['start_date'] = start_date or ''
        context['end_date'] = end_date or ''
        return context

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum, F, Avg
from django.http import JsonResponse
import json
from django.contrib.auth.decorators import login_required

class SalesReportView(ManagerRequiredMixin, LoginRequiredMixin, DateFilterMixin, ListView):
    model = Sale
    template_name = 'shop/sales_report.html'
    context_object_name = 'sales'
    paginate_by = 50

    def get_queryset(self):
        # 1. Get filtered sales
        sales_qs = Sale.objects.select_related('product', 'client')
        sales_qs = self.apply_date_filters(sales_qs)
        
        # 2. Get filtered invoice items
        items_qs = SaleItem.objects.select_related('product', 'invoice', 'invoice__client')
        original_date_field = getattr(self, 'date_field', 'date')
        self.date_field = 'invoice__date'
        items_qs = self.apply_date_filters(items_qs)
        self.date_field = original_date_field
        
        # 3. Combine and sort
        combined = list(sales_qs) + list(items_qs)
        combined.sort(key=lambda x: x.date, reverse=True)
        return combined

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the full queryset for statistics (before pagination)
        queryset = self.get_queryset()
        
        # Calculate summary statistics
        total_revenue = sum(sale.total_price for sale in queryset)
        total_cost = sum(sale.total_cost for sale in queryset if sale.total_cost)
        total_profit = sum(sale.profit for sale in queryset if hasattr(sale, 'profit') and sale.profit)
        
        cash_sales = [s for s in queryset if not s.is_credit]
        credit_sales = [s for s in queryset if s.is_credit]
        
        cash_revenue = sum(sale.total_price for sale in cash_sales)
        credit_revenue = sum(sale.total_price for sale in credit_sales)
        
        # Calculate outstanding credit
        # Since SaleItem amount_paid is 0 and we don't want to double count invoice payments,
        # we calculate total unpaid by summing over Sales and unique Invoices.
        sales_only_credit = [s for s in credit_sales if isinstance(s, Sale)]
        total_unpaid = sum(s.total_price - s.amount_paid for s in sales_only_credit)
        
        unique_credit_invoices = set(item.invoice for item in credit_sales if hasattr(item, 'invoice'))
        total_unpaid += sum(inv.total_price - inv.amount_paid for inv in unique_credit_invoices)
        
        # Calculate debt payments per client to avoid double-counting
        debt_payments_total = 0
        unique_clients = set()
        for sale in credit_sales:
            if sale.client and sale.client not in unique_clients:
                debt_payments_total += sum(p.amount for p in sale.client.debt_payments.all())
                unique_clients.add(sale.client)
        
        outstanding_credit = total_unpaid - debt_payments_total
        
        # Get filter values for form
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        
        context.update({
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'cash_revenue': cash_revenue,
            'credit_revenue': credit_revenue,
            'outstanding_credit': outstanding_credit,
            'total_sales': len(queryset),
            'cash_sales_count': len(cash_sales),
            'credit_sales_count': len(credit_sales),
            'start_date': start_date,
            'end_date': end_date,
        })
        
        return context

class ExpensesReportView(ManagerRequiredMixin, LoginRequiredMixin, DateFilterMixin, ListView):
    model = MoneyJournal
    template_name = 'shop/expenses_report.html'
    context_object_name = 'expenses'
    paginate_by = 50

    def get_queryset(self):
        queryset = MoneyJournal.objects.filter(entry_type='Expense').select_related('category').order_by('-date')
        return self.apply_date_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the full queryset for statistics (before pagination)
        queryset = self.get_queryset()
        
        # Calculate summary statistics
        total_expenses = sum(expense.amount for expense in queryset)
        
        # Group by category
        category_totals = {}
        for expense in queryset:
            category_name = expense.category.name if expense.category else 'Uncategorized'
            if category_name not in category_totals:
                category_totals[category_name] = 0
            category_totals[category_name] += expense.amount
        
        # Get filter values for form
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        
        context.update({
            'total_expenses': total_expenses,
            'category_totals': category_totals,
            'expense_count': len(queryset),
            'average_expense': total_expenses / len(queryset) if len(queryset) > 0 else 0,
            'start_date': start_date,
            'end_date': end_date,
        })
        
        return context

class MoneyJournalDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = MoneyJournal
    template_name = 'shop/money_confirm_delete.html'
    success_url = reverse_lazy('money_journal')

    def form_valid(self, form):
        messages.success(self.request, "Journal entry deleted successfully.")
        return super().form_valid(form)

class ReceiptPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        sale = get_object_or_404(Sale, pk=pk)
        template = get_template('shop/receipt_pdf.html')
        context = {
            'sale': sale,
            'current_date': timezone.now(),
        }
        html = template.render(context)
        response = HttpResponse(content_type='application/pdf')
        # inline displays in browser, attachment downloads
        response['Content-Disposition'] = f'inline; filename="receipt_{sale.id}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        if pisa_status.err:
            return HttpResponse('We had some errors <pre>' + html + '</pre>')
        return response

@login_required
@require_POST
def quick_stock_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    action = request.POST.get('action')
    
    if action == 'add':
        product.current_stock += 1
        InventoryMovement.objects.create(
            product=product,
            movement_type='IN',
            quantity=1,
            reference='Quick Adjustment (+1)'
        )
        messages.success(request, f"Added 1 to {product.name} stock.")
    elif action == 'remove':
        if product.current_stock > 0:
            product.current_stock -= 1
            InventoryMovement.objects.create(
                product=product,
                movement_type='OUT',
                quantity=1,
                reference='Quick Adjustment (-1)'
            )
            messages.success(request, f"Removed 1 from {product.name} stock.")
        else:
            messages.warning(request, f"{product.name} stock is already 0.")
            
    product.save()
    return redirect(request.META.get('HTTP_REFERER', 'product_list'))

class InvoiceCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'shop/invoice_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clients'] = Client.objects.all()
        context['products'] = Product.objects.all().order_by('name')
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            client_id = data.get('client_id')
            is_credit = data.get('is_credit', False)
            amount_paid = float(data.get('amount_paid', 0))
            items_data = data.get('items', [])

            if not items_data:
                return JsonResponse({'success': False, 'error': 'No items in the invoice.'})

            client = Client.objects.get(id=client_id) if client_id else None

            # Create Invoice
            invoice = Invoice.objects.create(
                client=client,
                is_credit=is_credit,
                amount_paid=amount_paid
            )

            total_sale_price = 0

            # Process items
            for item in items_data:
                product = Product.objects.get(id=item['product_id'])
                quantity = int(item['quantity'])
                price = float(item['price'])

                if quantity <= 0:
                    continue

                if product.current_stock < quantity:
                    raise ValueError(f"Not enough stock for {product.name}")

                # Calculate FIFO cost price
                cost_price = product.get_fifo_cost_price(quantity)
                product.deduct_from_batches(quantity)

                # Update current stock
                product.current_stock -= quantity
                product.save()

                # Create SaleItem
                SaleItem.objects.create(
                    invoice=invoice,
                    product=product,
                    quantity=quantity,
                    price_at_sale=price,
                    cost_price=cost_price
                )

                # Create InventoryMovement OUT
                InventoryMovement.objects.create(
                    product=product,
                    invoice=invoice,
                    movement_type='OUT',
                    quantity=quantity,
                    reference=f'Invoice #{invoice.id}',
                    cost_price=cost_price
                )

                total_sale_price += (quantity * price)

            # Create MoneyJournal entry for the amount paid (if any) or if it's cash (the full amount)
            amount_received = amount_paid if is_credit else total_sale_price
            if amount_received > 0:
                description = f"Invoice #{invoice.id}"
                if client:
                    description += f" - {client.name}"

                MoneyJournal.objects.create(
                    entry_type='Income',
                    amount=amount_received,
                    description=description,
                    invoice=invoice,
                    date=invoice.date
                )

            return JsonResponse({'success': True, 'invoice_id': invoice.id})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'shop/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    ordering = ['-date']

class InvoiceDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Invoice
    template_name = 'shop/invoice_confirm_delete.html'
    success_url = reverse_lazy('invoice_list')

    @transaction.atomic
    def form_valid(self, form):
        invoice = self.get_object()
        
        # Restore stock for each item
        for item in invoice.items.all():
            product = item.product
            product.current_stock += item.quantity
            product.save()
            
            # Create compensation stock-in to restore batches
            InventoryMovement.objects.create(
                product=product,
                movement_type='IN',
                quantity=item.quantity,
                remaining_quantity=item.quantity,
                reference=f'Invoice {invoice.id} deleted',
                cost_price=item.cost_price
            )

        messages.success(self.request, f"Invoice #{invoice.id} deleted and stock restored.")
        return super().form_valid(form)

class InvoiceReceiptPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        template = get_template('shop/invoice_receipt_pdf.html')
        context = {
            'invoice': invoice,
            'current_date': timezone.now(),
        }
        html = template.render(context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.id}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        if pisa_status.err:
            return HttpResponse('We had some errors <pre>' + html + '</pre>')
        return response
