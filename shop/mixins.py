from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect

class ManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser or 
            self.request.user.groups.filter(name='Manager').exists()
        )

    def handle_no_permission(self):
        # Redirect to product list if not authorized
        return redirect('product_list')

from django.utils import timezone

class DateFilterMixin:
    date_field = 'date'
    
    def apply_date_filters(self, queryset):
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_dt = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                start_dt = timezone.make_aware(start_dt)
                queryset = queryset.filter(**{f"{self.date_field}__gte": start_dt})
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                end_dt = timezone.make_aware(end_dt.replace(hour=23, minute=59, second=59))
                queryset = queryset.filter(**{f"{self.date_field}__lte": end_dt})
            except ValueError:
                pass
                
        return queryset
