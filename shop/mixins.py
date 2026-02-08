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
