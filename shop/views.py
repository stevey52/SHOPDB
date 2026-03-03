from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.contrib import messages
from .models import Product, InventoryMovement, Sale, MoneyJournal, ExpenseCategory, Client, DebtPayment
from .forms import SaleForm, MovementForm, MoneyJournalForm, ClientForm, DebtPaymentForm
from .mixins import ManagerRequiredMixin

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
            sales_data.append(float(daily_sales))
            
            # Daily COGS
            daily_cogs = Sale.objects.filter(date__date=date).aggregate(
                total=Sum(F('quantity') * F('product__cost_price'))
            )['total'] or 0
            
            # Manual Expenses for the day
            daily_expenses = MoneyJournal.objects.filter(entry_type='Expense', date__date=date).aggregate(
                total=Sum('amount')
            )['total'] or 0
            expenses_data.append(float(daily_expenses))
            
            # Profit = Total Sales Value - COGS - Expenses (Accrual)
            # This ensures that credit sales don't look like losses because of COGS.
            daily_profit = float(daily_sales) - float(daily_cogs) - float(daily_expenses)
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
        queryset = super().get_queryset()
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
        return context

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'shop/client_form.html'
    success_url = reverse_lazy('client_list')

class InventoryHistoryView(LoginRequiredMixin, ListView):
    model = InventoryMovement
    template_name = 'shop/inventory_history.html'
    context_object_name = 'movements'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__date__lte=end_date)
            
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

class SalesHistoryView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'shop/sales_history.html'
    context_object_name = 'sales'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__date__lte=end_date)
            
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

class MoneyJournalView(ManagerRequiredMixin, LoginRequiredMixin, ListView):
    model = MoneyJournal
    template_name = 'shop/money_journal.html'
    context_object_name = 'entries'
    ordering = ['-date']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__date__lte=end_date)
            
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
        # 1. Update Product Stock
        product = sale.product
        product.current_stock -= sale.quantity
        product.save()

        # 2. Record Inventory Movement (OUT)
        InventoryMovement.objects.create(
            product=product,
            sale=sale,
            movement_type='OUT',
            quantity=sale.quantity,
            date=sale.date,
            reference=f'Sale ID: {sale.id}'
        )

        # 3. Record Money Journal Entry (Income)
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
            if qty_added and int(qty_added) > 0:
                qty = int(qty_added)
                product = Product.objects.get(pk=pid)
                
                # 1. Update stock
                product.current_stock += qty
                product.save()
                
                # 2. Record movement
                InventoryMovement.objects.create(
                    product=product,
                    movement_type='IN',
                    quantity=qty,
                    date=movement_date,
                    reference=reference
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

    @transaction.atomic
    def form_valid(self, form):
        movement = form.save()
        # Update Product Stock
        product = movement.product
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

class ProfitReportView(ManagerRequiredMixin, LoginRequiredMixin, ListView):
    model = Product
    template_name = 'shop/profit_report.html'
    ordering = ['name']
    
    def get_queryset(self):
        # Annotate with total quantity sold and total revenue
        return Product.objects.annotate(
            total_sold=Sum('sales__quantity'),
            total_revenue=Sum(F('sales__quantity') * F('sales__price_at_sale'))
        ).filter(total_sold__gt=0) # Only show products that have sold

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        products_data = []
        total_revenue_sum = 0
        total_profit_sum = 0

        # Process each product to calculate profit based on current cost price
        for product in context['object_list']:
            total_sold = product.total_sold or 0
            # Convert Decimal to float for calculations if needed, but keeping Decimal is better for currency
            total_revenue = product.total_revenue or 0
            
            # Using current cost price as estimate
            unit_cost = product.cost_price or 0
            total_cost = total_sold * unit_cost
            
            net_profit = total_revenue - total_cost
            
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
        return context

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

class MoneyJournalDeleteView(ManagerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = MoneyJournal
    template_name = 'shop/money_confirm_delete.html'
    success_url = reverse_lazy('money_journal')

    def form_valid(self, form):
        messages.success(self.request, "Journal entry deleted successfully.")
        return super().form_valid(form)

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
