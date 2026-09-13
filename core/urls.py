from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin_view, name='signin'),
    path('marketplace/', views.marketplace_view, name='marketplace'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('farmer-dashboard/', views.farmer_dashboard_view, name='farmer_dashboard'),
    path('delivery-dashboard/', views.delivery_dashboard_view, name='delivery_dashboard'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('traceability/', views.traceability_view, name='traceability'),
    path('notifications/', views.notifications_view, name='notifications'),
]
