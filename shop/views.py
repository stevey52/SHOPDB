from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from .models import Product, InventoryMovement, Sale, MoneyJournal
from .forms import SaleForm, MovementForm, MoneyJournalForm

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
        context['total_income'] = MoneyJournal.objects.filter(entry_type='Income').aggregate(Sum('amount'))['amount__sum'] or 0
        context['total_expense'] = MoneyJournal.objects.filter(entry_type='Expense').aggregate(Sum('amount'))['amount__sum'] or 0
        context['balance'] = context['total_income'] - context['total_expense']
        
        # Calculate last 7 days data
        days = []
        sales_data = []
        profit_data = []
        expenses_data = []
        
        for i in range(6, -1, -1):
            date = timezone.now().date() - timezone.timedelta(days=i)
            days.append(date.strftime('%b %d'))
            
            # Daily Sales
            daily_sales = Sale.objects.filter(date__date=date).aggregate(
                total=Sum(F('quantity') * F('price_at_sale'))
            )['total'] or 0
            sales_data.append(float(daily_sales))
            
            # Daily Profit (Revenue - Cost of Goods Sold)
            daily_revenue = daily_sales
            daily_cogs = Sale.objects.filter(date__date=date).aggregate(
                total=Sum(F('quantity') * F('product__cost_price'))
            )['total'] or 0
            
            # Manual Expenses for the day
            daily_expenses = MoneyJournal.objects.filter(entry_type='Expense', date__date=date).aggregate(
                total=Sum('amount')
            )['total'] or 0
            expenses_data.append(float(daily_expenses))
            
            # Profit = Revenue - COGS - Expenses
            daily_profit = float(daily_revenue) - float(daily_cogs) - float(daily_expenses)
            profit_data.append(daily_profit)

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

    @transaction.atomic
    def form_valid(self, form):
        # Get the original product from the database to compare stock
        original_product = Product.objects.get(pk=self.object.pk)
        old_stock = original_product.current_stock
        
        # Save the form to update the product
        response = super().form_valid(form)
        new_stock = self.object.current_stock

        # Check if stock has changed
        if old_stock != new_stock:
            diff = new_stock - old_stock
            movement_type = 'IN' if diff > 0 else 'OUT'
            quantity = abs(diff)

            InventoryMovement.objects.create(
                product=self.object,
                movement_type=movement_type,
                quantity=quantity,
                reference='Manual Stock Update'
            )

        return response

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'shop/product_confirm_delete.html'
    success_url = reverse_lazy('product_list')

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
            queryset = queryset.filter(product__name__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context

class MoneyJournalView(LoginRequiredMixin, ListView):
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
            
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(description__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context

class LowStockView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'shop/product_list.html'
    context_object_name = 'products'
    
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
            movement_type='OUT',
            quantity=sale.quantity,
            reference=f'Sale ID: {sale.id}'
        )

        # 3. Record Money Journal Entry (Income)
        MoneyJournal.objects.create(
            entry_type='Income',
            amount=sale.total_price,
            description=f'Sale of {product.name} (x{sale.quantity})'
        )
        return super().form_valid(form)

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

class MoneyJournalCreateView(LoginRequiredMixin, CreateView):
    model = MoneyJournal
    form_class = MoneyJournalForm
    template_name = 'shop/journal_form.html'
    success_url = reverse_lazy('money_journal')
