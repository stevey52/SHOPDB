from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('inventory/', views.InventoryHistoryView.as_view(), name='inventory_history'),
    path('inventory/add/', views.MovementCreateView.as_view(), name='inventory_create'),
    path('sales/', views.SalesHistoryView.as_view(), name='sales_history'),
    path('sales/add/', views.SaleCreateView.as_view(), name='sale_create'),
    path('money/', views.MoneyJournalView.as_view(), name='money_journal'),
    path('money/add/', views.MoneyJournalCreateView.as_view(), name='money_create'),
    path('profit-report/', views.ProfitReportView.as_view(), name='profit_report'),
    path('categories/', views.ExpenseCategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.ExpenseCategoryCreateView.as_view(), name='category_create'),
    path('low-stock/', views.LowStockView.as_view(), name='low_stock'),
    path('products/<int:pk>/quick-stock/', views.quick_stock_update, name='quick_stock_update'),
]
