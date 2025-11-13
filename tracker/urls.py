from django.urls import path
from . import views

urlpatterns = [
    path('', views.expense_list, name='expense_list'),
    path('add/', views.add_expense, name='add_expense'),
    path('edit/<int:id>/', views.edit_expense, name='edit_expense'),
    path('delete/<int:id>/', views.delete_expense, name='delete_expense'),

    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Export/Backup/Restore
    path('export_csv/', views.export_csv, name='export_csv'),
    path('export_xlsx/', views.export_xlsx, name='export_xlsx'),
    path('backup_json/', views.backup_json, name='backup_json'),
    path('restore_json/', views.restore_json, name='restore_json'),
]
