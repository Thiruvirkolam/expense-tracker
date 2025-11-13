from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from .models import Expense
from datetime import datetime
import csv, json
import openpyxl

# ---------------- AUTH VIEWS ----------------
def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm = request.POST.get('confirm')
        if password != confirm:
            return render(request, 'tracker/signup.html', {'error': 'Passwords do not match.'})
        if User.objects.filter(username=username).exists():
            return render(request, 'tracker/signup.html', {'error': 'Username already taken.'})
        User.objects.create_user(username=username, password=password)
        return redirect('login')
    return render(request, 'tracker/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('expense_list')
        else:
            return render(request, 'tracker/login.html', {'error': 'Invalid username or password.'})
    return render(request, 'tracker/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------- EXPENSE VIEWS ----------------
@login_required(login_url='login')
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')

    # --- Filters ---
    category = request.GET.get('category')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    search = request.GET.get('search')

    if category:
        expenses = expenses.filter(category=category)
    if start_date and end_date:
        expenses = expenses.filter(date__range=[start_date, end_date])
    elif start_date:
        expenses = expenses.filter(date__gte=start_date)
    elif end_date:
        expenses = expenses.filter(date__lte=end_date)
    if search:
        expenses = expenses.filter(Q(title__icontains=search) | Q(notes__icontains=search))

    # --- Totals & Chart Data ---
    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    category_data = expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    categories = [item['category'] for item in category_data]
    category_totals = [float(item['total']) for item in category_data]

    monthly_data = expenses.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
    months = [item['month'].strftime("%b %Y") for item in monthly_data]
    monthly_totals = [float(item['total']) for item in monthly_data]

    return render(request, 'tracker/expense_list.html', {
        'expenses': expenses,
        'total': total,
        'categories': categories,
        'category_totals': category_totals,
        'months': months,
        'monthly_totals': monthly_totals,
        'search': search or '',
        'selected_category': category or '',
        'start_date': start_date or '',
        'end_date': end_date or '',
    })


@login_required(login_url='login')
def add_expense(request):
    if request.method == 'POST':
        Expense.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            amount=request.POST.get('amount'),
            category=request.POST.get('category'),
            date=request.POST.get('date'),
            notes=request.POST.get('notes'),
            recurring=('recurring' in request.POST),
            recurrence_type=request.POST.get('recurrence_type', 'NONE')
        )
        return redirect('expense_list')
    return render(request, 'tracker/add_expense.html')


@login_required(login_url='login')
def edit_expense(request, id):
    expense = get_object_or_404(Expense, id=id, user=request.user)
    if request.method == 'POST':
        expense.title = request.POST.get('title')
        expense.amount = request.POST.get('amount')
        expense.category = request.POST.get('category')
        expense.date = request.POST.get('date')
        expense.notes = request.POST.get('notes')
        expense.recurring = ('recurring' in request.POST)
        expense.recurrence_type = request.POST.get('recurrence_type', 'NONE')
        expense.save()
        return redirect('expense_list')
    return render(request, 'tracker/edit_expense.html', {'expense': expense})


@login_required(login_url='login')
def delete_expense(request, id):
    expense = get_object_or_404(Expense, id=id, user=request.user)
    expense.delete()
    return redirect('expense_list')


# ---------------- EXPORT CSV ----------------
@login_required(login_url='login')
def export_csv(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(['Title', 'Amount', 'Category', 'Date', 'Notes'])
    for exp in expenses:
        writer.writerow([exp.title, exp.amount, exp.category, exp.date, exp.notes])
    return response


# ---------------- EXPORT XLSX ----------------
@login_required(login_url='login')
def export_xlsx(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Expenses"
    sheet.append(['Title', 'Amount', 'Category', 'Date', 'Notes'])
    for exp in expenses:
        sheet.append([exp.title, float(exp.amount), exp.category, exp.date.strftime("%Y-%m-%d"), exp.notes])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=expenses.xlsx'
    workbook.save(response)
    return response


# ---------------- BACKUP JSON ----------------
@login_required(login_url='login')
def backup_json(request):
    expenses = Expense.objects.filter(user=request.user)
    data = list(expenses.values())
    response = HttpResponse(json.dumps(data, default=str), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=backup.json'
    return response


# ---------------- RESTORE JSON ----------------
@login_required(login_url='login')
def restore_json(request):
    if request.method == 'POST' and request.FILES.get('backup_file'):
        file = request.FILES['backup_file']
        data = json.load(file)
        for item in data:
            Expense.objects.update_or_create(
                user=request.user,
                title=item['title'],
                amount=item['amount'],
                category=item['category'],
                date=item['date'],
                notes=item.get('notes', ''),
                recurring=item.get('recurring', False),
                recurrence_type=item.get('recurrence_type', 'NONE')
            )
        return redirect('expense_list')
    return render(request, 'tracker/restore.html')
