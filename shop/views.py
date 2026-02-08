from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from .models import Product, InventoryMovement, Sale, MoneyJournal, ExpenseCategory
from .forms import SaleForm, MovementForm, MoneyJournalForm
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
