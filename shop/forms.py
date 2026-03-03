from django import forms
from .models import Product, InventoryMovement, Sale, MoneyJournal, Client, DebtPayment

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Address', 'rows': 2}),
        }

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['product', 'client', 'quantity', 'price_at_sale', 'date', 'is_credit', 'amount_paid']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'price_at_sale': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_credit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        is_credit = cleaned_data.get('is_credit')
        amount_paid = cleaned_data.get('amount_paid')
        client = cleaned_data.get('client')

        if product and quantity:
            if product.current_stock < quantity:
                raise forms.ValidationError(f"Insufficient stock! Only {product.current_stock} units available.")
        
        if is_credit and not client:
            raise forms.ValidationError("A client must be selected for credit sales.")
            
        return cleaned_data

class DebtPaymentForm(forms.ModelForm):
    class Meta:
        model = DebtPayment
        fields = ['client', 'amount', 'date', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Payment amount must be a positive number greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        client = cleaned_data.get('client')

        if client and amount:
            outstanding = client.total_debt
            if outstanding <= 0:
                raise forms.ValidationError(
                    f"{client.name} has no outstanding debt (balance: TZS {outstanding:,.2f}). "
                    "Please verify before recording a payment."
                )
            if amount > outstanding:
                raise forms.ValidationError(
                    f"Payment of TZS {amount:,.2f} exceeds {client.name}'s outstanding debt of "
                    f"TZS {outstanding:,.2f}. Please enter a correct amount."
                )
        return cleaned_data

class MovementForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ['product', 'movement_type', 'quantity', 'reference']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'movement_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
        }

class MoneyJournalForm(forms.ModelForm):
    class Meta:
        model = MoneyJournal
        fields = ['entry_type', 'amount', 'category', 'description']
        widgets = {
            'entry_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
