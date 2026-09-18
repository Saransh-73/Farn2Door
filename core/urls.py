from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.signin_view, name='signin'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('marketplace/', views.marketplace_view, name='marketplace'),
    path('cart/sync/', views.cart_sync_view, name='cart_sync'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('orders/create/', views.create_order_view, name='create_order'),
    path('farmer-dashboard/', views.farmer_dashboard_view, name='farmer_dashboard'),
    path('farmer/listings/create/', views.farmer_listing_create_view, name='farmer_listing_create'),
    path('farmer/orders/<int:order_id>/accept/', views.farmer_order_accept_view, name='farmer_order_accept'),
    path('delivery-dashboard/', views.delivery_dashboard_view, name='delivery_dashboard'),
    path('bulk-buyer-dashboard/', views.bulk_buyer_dashboard_view, name='bulk_buyer_dashboard'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('traceability/', views.traceability_view, name='traceability'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('api/chatbot/', views.chatbot_api_view, name='chatbot_api'),
]
