from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from farms.permissions import any_member_required, edit_delete_required, log_activity_required
from inventory.models import InventoryItem
from inventory.services import record_milk_sale
from notifications.models import Notification
from notifications.services import notify

from .forms import MilkSaleForm, TransactionForm
from .models import Transaction


@any_member_required
def transaction_list(request):
    transactions = Transaction.objects.filter(farm=request.farm)[:100]
    totals = Transaction.objects.filter(farm=request.farm).aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    income = totals['income'] or 0
    expense = totals['expense'] or 0
    context = {
        'transactions': transactions,
        'income': income,
        'expense': expense,
        'net': income - expense,
    }
    return render(request, 'finance/transaction_list.html', context)


@log_activity_required
def transaction_create(request):
    form = TransactionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        transaction = form.save(commit=False)
        transaction.farm = request.farm
        transaction.recorded_by = request.user
        transaction.save()
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'transaction',
            f'{transaction.get_kind_display()} - {transaction.amount} ({transaction.get_category_display()})'
        )
        messages.success(request, f'{transaction.get_kind_display()} of {transaction.amount} recorded.')
        return redirect('finance:transaction_list')
    return render(request, 'finance/transaction_form.html', {'form': form})


@log_activity_required
def milk_sale_create(request):
    form = MilkSaleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        liters = form.cleaned_data['liters']
        amount = form.cleaned_data['amount']
        date = form.cleaned_data['date']
        note = form.cleaned_data['note']

        description = f'{liters}L milk sale' + (f' - {note}' if note else '')
        transaction = Transaction.objects.create(
            farm=request.farm, kind=Transaction.Kind.INCOME, category=Transaction.Category.SALES,
            amount=amount, date=date, note=description, recorded_by=request.user,
        )
        milk_item = InventoryItem.objects.filter(farm=request.farm, name='Milk').first()
        stock_before = milk_item.current_stock if milk_item else 0
        record_milk_sale(request.farm, liters, date, request.user)
        notify(request.farm, request.user, Notification.Verb.CREATED, 'transaction', description)

        messages.success(request, f'Milk sale of {liters}L for {amount} recorded.')
        if stock_before - liters < 0:
            messages.warning(request, 'Milk stock is now negative - check for missing production records.')
        return redirect('finance:transaction_list')
    return render(request, 'finance/milk_sale_form.html', {'form': form})


@edit_delete_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, farm=request.farm)
    form = TransactionForm(request.POST or None, instance=transaction)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'transaction',
            f'{transaction.get_kind_display()} - {transaction.amount} ({transaction.get_category_display()})'
        )
        messages.success(request, 'Transaction updated.')
        return redirect('finance:transaction_list')
    return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction})


@edit_delete_required
def transaction_delete(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, farm=request.farm)
    if request.method == 'POST':
        description = f'{transaction.get_kind_display()} - {transaction.amount} ({transaction.get_category_display()})'
        transaction.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'transaction', description)
        messages.success(request, 'Transaction deleted.')
    return redirect('finance:transaction_list')
