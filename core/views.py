from django.shortcuts import render


def home(request):
    """Renders the public landing page."""
    return render(request, 'index.html')


def login_view(request):
    """Renders the role-based login page (Farmer, Consumer, Bulk, Delivery, Admin)."""
    return render(request, 'login.html')


def signin_view(request):
    """Renders the OTP-based sign-in / registration page."""
    return render(request, 'signin.html')


def marketplace_view(request):
    """Renders the marketplace browsing and cart page."""
    return render(request, 'marketplace.html')


def checkout_view(request):
    """Renders the checkout and order placement page."""
    return render(request, 'checkout.html')


def farmer_dashboard_view(request):
    """Renders the farmer inventory and earnings dashboard."""
    return render(request, 'farmer-dashboard.html')


def delivery_dashboard_view(request):
    """Renders the delivery partner route and tasks dashboard."""
    return render(request, 'delivery-dashboard.html')


def admin_dashboard_view(request):
    """Renders the admin platform oversight and verification dashboard."""
    return render(request, 'admin-dashboard.html')


def traceability_view(request):
    """Renders the farm-to-door batch traceability and tracking page."""
    return render(request, 'traceability.html')


def notifications_view(request):
    """Renders the unified notifications center."""
    return render(request, 'notifications.html')
