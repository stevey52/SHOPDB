from django import forms
from .models import Product, InventoryMovement, Sale, MoneyJournal

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['product', 'quantity', 'price_at_sale']

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        if product and quantity:
            if product.current_stock < quantity:
                raise forms.ValidationError(f"Insufficient stock! Only {product.current_stock} units available.")
        return cleaned_data

class MovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ['product', 'movement_type', 'quantity', 'reference']

class MoneyJournalForm(forms.ModelForm):
    class Meta:
        model = MoneyJournal
        fields = ['entry_type', 'amount', 'description']
