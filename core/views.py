import json
import os
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

from .models import Account, Order, OrderItem, Product


def home(request):
    """Renders the public landing page."""
    return render(request, 'index.html')


def login_view(request):
    """Renders the role-based login page (Farmer, Consumer, Bulk, Delivery, Admin)."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        clean_phone = ''.join(c for c in phone if c.isdigit())[-10:]
        name = request.POST.get('name', '').strip()
        password = request.POST.get('password', '')

        account = None
        if email and (clean_phone or phone):
            account = Account.objects.filter(email__iexact=email, phone__in=[phone, clean_phone]).first()
        if not account and email:
            account = Account.objects.filter(email__iexact=email).first()
        if not account and (clean_phone or phone):
            account = Account.objects.filter(phone__in=[phone, clean_phone]).first()
        if not account and name and email:
            account = Account.objects.filter(name__iexact=name, email__iexact=email).first()

        if account and check_password(password, account.password_hash):
            request.session['account_id'] = account.pk
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(_dashboard_for_role(account.role))
        return render(request, 'login.html', {
            'login_error': 'Email, mobile number, password, or role is incorrect.',
            'submitted_name': name,
            'submitted_email': email,
            'submitted_phone': phone,
        }, status=401)
    return render(request, 'login.html')



def signin_view(request):
    """Renders the OTP-based sign-in / registration page."""
    return render(request, 'signin.html')


def register_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST is required.'}, status=405)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        payload = request.POST

    email = payload.get('email', '').strip().lower()
    phone = payload.get('phone', '').strip()
    password = payload.get('password', '')
    name = payload.get('name', '').strip()
    role = payload.get('role', 'consumer')
    if not email or not phone or not password:
        return JsonResponse({'error': 'Email, mobile number, and password are required.'}, status=400)
    if not Account.objects.filter(email=email).exists() and not Account.objects.filter(phone=phone).exists():
        account = Account.objects.create(
            name=name,
            email=email,
            phone=phone,
            role=role if role in dict(Account.ROLE_CHOICES) else 'consumer',
            password_hash=make_password(password),
        )
        request.session['account_id'] = account.pk
        return JsonResponse({'redirect': '/' + str(_dashboard_for_role(account.role).replace('_', '-')) + '/'})
    return JsonResponse({'error': 'An account already exists with this email or mobile number.'}, status=409)


def profile_view(request):
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    if not account:
        return redirect(f'/login/?next=/profile/')
    return render(request, 'profile.html', {'account': account})


def logout_view(request):
    request.session.flush()
    return redirect('login')


def _dashboard_for_role(role):
    return {
        'farmer': 'farmer_dashboard',
        'consumer': 'marketplace',
        'bulk': 'bulk_buyer_dashboard',
        'delivery': 'delivery_dashboard',
        'admin': 'admin_dashboard',
    }.get(role, 'marketplace')


def marketplace_view(request):
    """Renders the marketplace browsing and cart page."""
    products = Product.objects.filter(is_active=True).values(
        'id', 'name', 'category', 'description', 'unit', 'price', 'stock_quantity', 'farmer_name'
    )
    return render(request, 'marketplace.html', {
        'marketplace_products': list(products),
        'cart_items': list(request.session.get('cart_items', {}).values()),
    })


@ensure_csrf_cookie
def checkout_view(request):
    """Renders the checkout and order placement page."""
    return render(request, 'checkout.html', {
        'cart_items': list(request.session.get('cart_items', {}).values()),
    })


def cart_sync_view(request):
    """Stores the current marketplace cart in the user's session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST is required.'}, status=405)
    try:
        payload = json.loads(request.body)
    except (TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid cart payload.'}, status=400)

    items = {}
    for raw_item in payload.get('items', []):
        try:
            product_id = int(raw_item['id'])
            quantity = int(raw_item['quantity'])
            price = Decimal(str(raw_item['price']))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return JsonResponse({'error': 'Invalid cart item.'}, status=400)
        if product_id <= 0 or quantity <= 0 or price < 0:
            return JsonResponse({'error': 'Invalid cart item.'}, status=400)
        item_data = {
            'id': product_id,
            'name': str(raw_item.get('name', '')).strip(),
            'unit': str(raw_item.get('unit', 'kg')).strip() or 'kg',
            'farmer': str(raw_item.get('farmer', '')).strip(),
            'price': str(price),
            'icon': str(raw_item.get('icon', '')),
            'cat': str(raw_item.get('cat', 'veg')),
            'img': str(raw_item.get('img', raw_item.get('image', ''))).strip(),
            'quantity': quantity,
        }
        standard_key = str(product_id)
        compatibility_key = f'str({product_id})'
        items[standard_key] = item_data
        items[compatibility_key] = item_data
    request.session['cart_items'] = items
    request.session.modified = True
    return JsonResponse({'item_count': sum(item['quantity'] for item in items.values())})


def create_order_view(request):
    """Creates an order from the session cart and clears it only on success."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST is required.'}, status=405)
    cart_items = request.session.get('cart_items', {})
    if not cart_items:
        return JsonResponse({'error': 'Your cart is empty.'}, status=400)
    try:
        payload = json.loads(request.body)
        customer_name = str(payload.get('name', '')).strip()
        customer_phone = str(payload.get('phone', '')).strip()
        address = str(payload.get('address', '')).strip()
        cod_fee = Decimal('15') if payload.get('payment_method') == 'cod' else Decimal('0')
        discount = Decimal('10') if payload.get('promo') == 'HARVEST10' else Decimal('0')
    except (TypeError, json.JSONDecodeError, InvalidOperation):
        return JsonResponse({'error': 'Invalid order payload.'}, status=400)
    if not customer_name or not customer_phone or not address:
        return JsonResponse({'error': 'Name, phone, and address are required.'}, status=400)

    try:
        with transaction.atomic():
            order = Order.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                delivery_address=address,
            )
            subtotal = Decimal('0')
            for item in cart_items.values():
                quantity = Decimal(str(item['quantity']))
                unit_price = Decimal(str(item['price']))
                product, _ = Product.objects.get_or_create(
                    pk=item['id'],
                    defaults={
                        'name': item['name'],
                        'category': item.get('cat', 'veg'),
                        'unit': item['unit'],
                        'price': unit_price,
                        'stock_quantity': 0,
                        'farmer_name': item['farmer'],
                    },
                )
                if product.price != unit_price:
                    return JsonResponse({'error': f'Price changed for {product.name}.'}, status=409)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                )
                subtotal += quantity * product.price
            delivery_fee = Decimal('0') if subtotal >= Decimal('500') else Decimal('40')
            order.total_amount = max(Decimal('0'), subtotal + delivery_fee + cod_fee - discount)
            order.save(update_fields=['total_amount'])
    except (KeyError, InvalidOperation, ValueError) as exc:
        return JsonResponse({'error': f'Invalid cart item: {exc}'}, status=400)

    request.session.pop('cart_items', None)
    request.session.modified = True
    return JsonResponse({'order_id': order.pk, 'total': str(order.total_amount)})


@ensure_csrf_cookie
def farmer_dashboard_view(request):
    """Renders the farmer inventory and earnings dashboard."""
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    if not account:
        return redirect(f'/login/?next=/farmer-dashboard/')
    if account.role != 'farmer':
        return redirect(_dashboard_for_role(account.role))
    farmer_products = Product.objects.filter(farmer_name__in=[account.name, account.email])
    orders = Order.objects.filter(items__product__farmer_name__in=[account.name, account.email]).distinct()
    return render(request, 'farmer-dashboard.html', {
        'account': account,
        'farmer_products': farmer_products,
        'orders': orders,
    })



def _farmer_account(request):
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    return account if account and account.role == 'farmer' else None


def farmer_listing_create_view(request):
    """Creates a listing for the farmer currently signed in."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST is required.'}, status=405)
    account = _farmer_account(request)
    if not account:
        return JsonResponse({'error': 'Farmer login required.'}, status=403)
    try:
        payload = json.loads(request.body)
        name = str(payload.get('name', '')).strip()
        quantity = Decimal(str(payload.get('quantity', '0')))
        price = Decimal(str(payload.get('price', '0')))
    except (TypeError, json.JSONDecodeError, InvalidOperation):
        return JsonResponse({'error': 'Invalid listing payload.'}, status=400)
    if not name or quantity <= 0 or price < 0:
        return JsonResponse({'error': 'Crop, quantity, and price are required.'}, status=400)

    next_product_id = (Product.objects.aggregate(max_id=Max('id'))['max_id'] or 0) + 1
    product = Product.objects.create(
        id=next_product_id,
        name=name,
        category='Produce',
        unit='kg',
        price=price,
        stock_quantity=quantity,
        farmer_name=account.name or account.email,
    )
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('core_product', 'id'), %s, true)",
                [product.pk],
            )
    return JsonResponse({
        'id': product.pk,
        'name': product.name,
        'quantity': str(product.stock_quantity),
        'price': str(product.price),
        'farmer': product.farmer_name,
    }, status=201)


def farmer_order_accept_view(request, order_id):
    """Accepts a pending order containing one of the farmer's products."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST is required.'}, status=405)
    account = _farmer_account(request)
    if not account:
        return JsonResponse({'error': 'Farmer login required.'}, status=403)
    order = Order.objects.filter(
        pk=order_id,
        status='pending',
        items__product__farmer_name=account.name or account.email,
    ).first()
    if not order:
        return JsonResponse({'error': 'Pending farmer order not found.'}, status=404)
    order.status = 'confirmed'
    order.save(update_fields=['status'])
    return JsonResponse({'order_id': order.pk, 'status': order.status})


def delivery_dashboard_view(request):
    """Renders the delivery partner route and tasks dashboard."""
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    if not account:
        return render(request, 'delivery-dashboard.html', {'account': None})
    if account.role != 'delivery':
        return redirect(_dashboard_for_role(account.role))
    return render(request, 'delivery-dashboard.html', {'account': account})


def admin_dashboard_view(request):
    """Renders the admin platform oversight and verification dashboard."""
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    if not account:
        return render(request, 'admin-dashboard.html', {'account': None})
    if account.role != 'admin':
        return redirect(_dashboard_for_role(account.role))
    # Provide summary stats for the admin dashboard KPI cards
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    total_accounts = Account.objects.count()
    total_products = Product.objects.filter(is_active=True).count()
    recent_orders = Order.objects.select_related().prefetch_related('items__product')[:10]
    return render(request, 'admin-dashboard.html', {
        'account': account,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_accounts': total_accounts,
        'total_products': total_products,
        'recent_orders': recent_orders,
    })


def bulk_buyer_dashboard_view(request):
    """Renders the professional B2B bulk procurement dashboard for hotels, restaurants, and caterers."""
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None

    # Establish business identity (defaulting to Sharma Restaurant for demo/evaluation if no name)
    business_name = 'Sharma Restaurant'
    if account and account.name:
        business_name = account.name
    elif account and account.email:
        business_name = account.email.split('@')[0].title() + " Procurement"

    # Bulk Produce catalog with accurate commodity images and wholesale slabs
    bulk_catalog = [
        {
            'id': 1001,
            'name': 'Grade-A Desi Tomatoes',
            'category': 'Vegetables',
            'farmer_name': 'Ramesh Patil',
            'fpo_name': 'Sahyadri Farmer Producer Co.',
            'location': 'Nashik, Maharashtra (42 km)',
            'price': 24.00,
            'slab_100': 22.00,
            'slab_500': 19.50,
            'unit': 'kg',
            'available_qty': 2800,
            'harvest_info': 'Harvested 6 hrs ago · Grade-A export sort · 100% Residue free',
            'image': 'https://commons.wikimedia.org/wiki/Special:FilePath/Tomatoes.jpg?width=700',
            'rating': 4.9,
            'reviews_count': 128,
            'min_order': 50,
            'badge': 'High Demand'
        },
        {
            'id': 1002,
            'name': 'Nashik Red Onions (Large Crate)',
            'category': 'Vegetables',
            'farmer_name': 'Suresh Yadav',
            'fpo_name': 'Lasalgaon Mandi Producers Co-op',
            'location': 'Lasalgaon, Nashik (58 km)',
            'price': 22.00,
            'slab_100': 20.00,
            'slab_500': 18.00,
            'unit': 'kg',
            'available_qty': 4500,
            'harvest_info': 'Sun-cured 48h · 55mm+ uniform grade · Zero rot guarantee',
            'image': 'https://commons.wikimedia.org/wiki/Special:FilePath/Onion_on_White.JPG?width=700',
            'rating': 4.8,
            'reviews_count': 214,
            'min_order': 100,
            'badge': 'Bestseller'
        },
        {
            'id': 1003,
            'name': 'Ooty Sweet Carrots (Hydro-Washed)',
            'category': 'Vegetables',
            'farmer_name': 'Sunita Farms',
            'fpo_name': 'Nilgiri Growers Association',
            'location': 'Ooty / Pune Hub (75 km)',
            'price': 32.00,
            'slab_100': 29.00,
            'slab_500': 26.00,
            'unit': 'kg',
            'available_qty': 1600,
            'harvest_info': 'Harvested 4 AM today · Pre-washed & sorted · High brix 8.2°',
            'image': 'https://images.unsplash.com/photo-1598170845058-32b9d6a5c317?auto=format&fit=crop&w=800&q=80',
            'rating': 4.9,
            'reviews_count': 94,
            'min_order': 50,
            'badge': 'Farm Fresh'
        },
        {
            'id': 1004,
            'name': 'Indore Jyoti Potatoes (Kitchen Grade)',
            'category': 'Vegetables',
            'farmer_name': 'Kailash Patel',
            'fpo_name': 'Malwa Krishi FPO, Indore',
            'location': 'Indore / Direct Hub (110 km)',
            'price': 18.00,
            'slab_100': 16.50,
            'slab_500': 14.80,
            'unit': 'kg',
            'available_qty': 6200,
            'harvest_info': 'Low sugar (<0.1%) · High dry matter · Ideal for culinary frying',
            'image': 'https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=800&q=80',
            'rating': 4.7,
            'reviews_count': 180,
            'min_order': 100,
            'badge': 'Culinary Grade'
        },
        {
            'id': 1005,
            'name': 'Ratnagiri Alphonso Mangoes (GI Tagged)',
            'category': 'Fruits',
            'farmer_name': 'Saransh Orchards',
            'fpo_name': 'Konkan Mango Growers Cooperative',
            'location': 'Ratnagiri, Maharashtra (120 km)',
            'price': 145.00,
            'slab_100': 132.00,
            'slab_500': 118.00,
            'unit': 'kg',
            'available_qty': 950,
            'harvest_info': 'Natural tree-ripened · Carb-free ripening · Brix 19+ sweet',
            'image': 'https://images.unsplash.com/photo-1553279768-865429fa0078?auto=format&fit=crop&w=900&q=85',
            'rating': 5.0,
            'reviews_count': 76,
            'min_order': 25,
            'badge': 'Premium GI'
        },
        {
            'id': 1006,
            'name': 'Grand Naine Robusta Bananas (Cushioned Crates)',
            'category': 'Fruits',
            'farmer_name': 'Anand Shinde',
            'fpo_name': 'Jalgaon Banana FPO Collective',
            'location': 'Jalgaon, Maharashtra (85 km)',
            'price': 34.00,
            'slab_100': 30.00,
            'slab_500': 27.00,
            'unit': 'kg',
            'available_qty': 3200,
            'harvest_info': 'Stage 3.5 uniform ripeness · Foam cushioned 13kg crates',
            'image': 'https://commons.wikimedia.org/wiki/Special:FilePath/Bananas_white_background.jpg?width=700',
            'rating': 4.8,
            'reviews_count': 112,
            'min_order': 50,
            'badge': 'Export Quality'
        },
        {
            'id': 1007,
            'name': 'Crisp Green Bell Peppers (Polyhouse)',
            'category': 'Vegetables',
            'farmer_name': 'Pravin Jadhav',
            'fpo_name': 'Shirdi Polyhouse Cluster',
            'location': 'Sangamner, Maharashtra (52 km)',
            'price': 38.00,
            'slab_100': 34.00,
            'slab_500': 31.00,
            'unit': 'kg',
            'available_qty': 1200,
            'harvest_info': 'Plucked 5 hrs ago · 4-lobed thick walls · Extended 7-day crispness',
            'image': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?auto=format&fit=crop&w=900&q=80',
            'rating': 4.8,
            'reviews_count': 64,
            'min_order': 30,
            'badge': 'Polyhouse'
        },
        {
            'id': 1008,
            'name': 'Snowball Cauliflower (Clean Trimmed Curd)',
            'category': 'Vegetables',
            'farmer_name': 'Balasaheb Gite',
            'fpo_name': 'Narayangaon Vegetable Cluster',
            'location': 'Narayangaon, Pune (46 km)',
            'price': 26.00,
            'slab_100': 23.00,
            'slab_500': 20.50,
            'unit': 'kg',
            'available_qty': 1800,
            'harvest_info': 'Tight snowy white curds · Leaves pre-trimmed for minimal kitchen prep',
            'image': 'https://cdn.britannica.com/27/78227-050-28A68F87/cauliflower-Head-colour-White-brown-cultivars.jpg',
            'rating': 4.7,
            'reviews_count': 82,
            'min_order': 50,
            'badge': 'Zero Waste'
        },
        {
            'id': 1009,
            'name': 'Hydroponic Baby Spinach / Palak (Crisp)',
            'category': 'Vegetables',
            'farmer_name': 'Meera Deshmukh',
            'fpo_name': 'GreenRoots Agro FPO, Pune',
            'location': 'Pune District (28 km)',
            'price': 30.00,
            'slab_100': 26.00,
            'slab_500': 22.00,
            'unit': 'kg',
            'available_qty': 800,
            'harvest_info': 'Cut 3 AM today · Hydro-washed and bunched in breathable crates',
            'image': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?auto=format&fit=crop&w=900&q=80',
            'rating': 4.9,
            'reviews_count': 59,
            'min_order': 20,
            'badge': 'Hydro-Washed'
        },
        {
            'id': 1010,
            'name': 'Traditional 1121 Steam Basmati Rice (2-Year Aged)',
            'category': 'Grains & Pulses',
            'farmer_name': 'Harinder Singh',
            'fpo_name': 'Taraori Basmati Growers Collective',
            'location': 'Karnal / Direct Agri Hub',
            'price': 78.00,
            'slab_100': 72.00,
            'slab_500': 66.00,
            'unit': 'kg',
            'available_qty': 8500,
            'harvest_info': '2-Year aged steam grain · 8.35mm kernel length · 50kg moisture-lock sacks',
            'image': 'https://cpimg.tistatic.com/06975915/b/4/Basmati-Raw-Rice.jpg',
            'rating': 4.9,
            'reviews_count': 320,
            'min_order': 100,
            'badge': 'Aged 2 Years'
        },
        {
            'id': 1011,
            'name': 'Pure Lakadong Turmeric (High Curcumin 7.5%)',
            'category': 'Spices',
            'farmer_name': 'Wanbiang Syiem',
            'fpo_name': 'Meghalaya Organic FPO',
            'location': 'Direct Spice Dispatch (APEDA Certified)',
            'price': 185.00,
            'slab_100': 168.00,
            'slab_500': 152.00,
            'unit': 'kg',
            'available_qty': 1100,
            'harvest_info': 'Sun-dried rhizomes · Lab certified 7.5% curcumin · No artificial color',
            'image': 'https://commons.wikimedia.org/wiki/Special:FilePath/Curcuma_longa_roots.jpg?width=700',
            'rating': 5.0,
            'reviews_count': 142,
            'min_order': 25,
            'badge': 'High Curcumin'
        },
        {
            'id': 1012,
            'name': 'Wayanad Single-Knot Fresh Ginger',
            'category': 'Spices',
            'farmer_name': 'Mathew Kurian',
            'fpo_name': 'Wayanad Spices Collective',
            'location': 'Wayanad / Western Ghats Hub',
            'price': 82.00,
            'slab_100': 74.00,
            'slab_500': 67.00,
            'unit': 'kg',
            'available_qty': 1450,
            'harvest_info': 'High aromatic oil content · Washed clean knots · Low fiber',
            'image': 'https://images.unsplash.com/photo-1522184216316-3c25379f9760?auto=format&fit=crop&w=900&q=80',
            'rating': 4.8,
            'reviews_count': 88,
            'min_order': 25,
            'badge': 'Aromatic'
        },
    ]

    # Active Bulk Orders for Sharma Restaurant
    active_orders = [
        {
            'order_id': 'F2D-BLK-8821',
            'products_summary': 'Nashik Red Onions (400 kg), Grade-A Tomatoes (250 kg)',
            'total_qty': '650 kg',
            'farmer_or_fpo': 'Sahyadri Farmer Producer Co.',
            'total_amount': 13650.00,
            'order_date': '18 Sep 2026, 08:30 AM',
            'status': 'In Transit',
            'status_class': 'transit',
            'eta': 'Today by 05:45 AM',
            'delivery_address': 'Central Kitchen, Plot 8B, MIDC Sector 14',
            'truck_no': 'MH-12-QX-4019',
            'temp_c': '4.2°C Cold Chain Active'
        },
        {
            'order_id': 'F2D-BLK-8819',
            'products_summary': 'Indore Jyoti Potatoes (500 kg), Ooty Carrots (150 kg)',
            'total_qty': '650 kg',
            'farmer_or_fpo': 'Malwa Krishi FPO, Indore',
            'total_amount': 11725.00,
            'order_date': '17 Sep 2026, 04:15 PM',
            'status': 'Pickup Scheduled',
            'status_class': 'pickup',
            'eta': 'Tomorrow, 06:00 AM',
            'delivery_address': 'Central Kitchen, Plot 8B, MIDC Sector 14',
            'truck_no': 'MP-09-GH-3120',
            'temp_c': 'Ambient Reefer'
        },
        {
            'order_id': 'F2D-BLK-8815',
            'products_summary': '1121 Basmati Rice (300 kg), Pure Lakadong Turmeric (50 kg)',
            'total_qty': '350 kg',
            'farmer_or_fpo': 'Taraori Basmati Collective',
            'total_amount': 29800.00,
            'order_date': '17 Sep 2026, 11:00 AM',
            'status': 'Accepted',
            'status_class': 'accepted',
            'eta': '20 Sep 2026, Early Morning',
            'delivery_address': 'Central Kitchen, Plot 8B, MIDC Sector 14',
            'truck_no': 'HR-05-AB-7741',
            'temp_c': 'Dry Moisture-Lock'
        },
        {
            'order_id': 'F2D-BLK-8809',
            'products_summary': 'Alphonso Mangoes (150 kg), Robusta Bananas (200 kg)',
            'total_qty': '350 kg',
            'farmer_or_fpo': 'Konkan Mango Growers Co-op',
            'total_amount': 25200.00,
            'order_date': '16 Sep 2026, 02:20 PM',
            'status': 'Delivered',
            'status_class': 'delivered',
            'eta': 'Delivered 17 Sep 2026',
            'delivery_address': 'Sharma Restaurant, Branch 1 (Main Hall)',
            'truck_no': 'MH-08-TR-1022',
            'temp_c': 'Verified 6.5°C'
        },
    ]

    # Verified Farming Partners
    farming_partners = [
        {
            'name': 'Sahyadri Farmer Producer Co.',
            'badge': 'Verified Tier-1 FPO',
            'location': 'Nashik, Maharashtra · 42 km',
            'rating': 4.9,
            'orders_completed': 142,
            'products': 'Tomatoes, Onions, Green Peppers',
            'acres': '1,400+ Acres Collective',
            'phone': '+91 98220 44102',
            'avatar_color': '#2E7D32'
        },
        {
            'name': 'Malwa Krishi FPO',
            'badge': 'Certified Potato Cluster',
            'location': 'Indore, Madhya Pradesh · 110 km',
            'rating': 4.8,
            'orders_completed': 96,
            'products': 'Kitchen Potatoes, Garlic, Grains',
            'acres': '950 Acres Member Network',
            'phone': '+91 97551 88390',
            'avatar_color': '#6D4C41'
        },
        {
            'name': 'Konkan Mango & Fruit Co-op',
            'badge': 'GI Certified & Organic',
            'location': 'Ratnagiri, Maharashtra · 120 km',
            'rating': 5.0,
            'orders_completed': 68,
            'products': 'Alphonso & Kesar Mangoes, Cashews',
            'acres': '620 Acres Orchards',
            'phone': '+91 94224 55109',
            'avatar_color': '#F9A825'
        },
        {
            'name': 'Nilgiri Growers Association',
            'badge': 'Cold-Climate Washed Roots',
            'location': 'Ooty / Pune Logistics Hub',
            'rating': 4.9,
            'orders_completed': 84,
            'products': 'Carrots, Beetroot, Cabbages',
            'acres': '480 Acres Mountain Farms',
            'phone': '+91 98410 77123',
            'avatar_color': '#4CAF50'
        },
    ]

    # Invoices
    invoices = [
        {
            'inv_no': 'INV-2026-0914',
            'order_id': 'F2D-BLK-8809',
            'date': '17 Sep 2026',
            'amount': '₹25,200.00',
            'items_count': '2 Commodities · 350 kg',
            'status': 'Paid (E-Way Bill Verified)',
            'gstin': '27AAACS1429B1ZX'
        },
        {
            'inv_no': 'INV-2026-0898',
            'order_id': 'F2D-BLK-8772',
            'date': '10 Sep 2026',
            'amount': '₹38,450.00',
            'items_count': '4 Commodities · 1,200 kg',
            'status': 'Paid (Direct NEFT Settlement)',
            'gstin': '27AAACS1429B1ZX'
        },
        {
            'inv_no': 'INV-2026-0870',
            'order_id': 'F2D-BLK-8724',
            'date': '03 Sep 2026',
            'amount': '₹44,100.00',
            'items_count': '5 Commodities · 1,500 kg',
            'status': 'Paid (Commercial Credit)',
            'gstin': '27AAACS1429B1ZX'
        },
    ]

    # Notifications
    notifications = [
        {
            'id': 1,
            'title': 'Cold-Chain Reefer Picked Up',
            'body': 'Order #F2D-BLK-8821 (650kg Onions & Tomatoes) departed Sahyadri FPO Nashik hub. Temperature stable at 4.2°C.',
            'time': '35 mins ago',
            'type': 'transit',
            'icon': '🚚'
        },
        {
            'id': 2,
            'title': 'Delivery Scheduled for 05:30 AM',
            'body': 'Driver Mahesh Rao (+91 98231 40192) will arrive at Central Kitchen Gate 2. Please keep weighbridge log ready.',
            'time': '1 hr ago',
            'type': 'alert',
            'icon': '⏰'
        },
        {
            'id': 3,
            'title': 'FPO Price Drop Alert: Shirdi Polyhouse',
            'body': 'Green Bell Peppers reduced by ₹4/kg for bulk allocations exceeding 200kg this week.',
            'time': '3 hrs ago',
            'type': 'price',
            'icon': '📉'
        },
        {
            'id': 4,
            'title': 'Weekly Harvest Booking Open',
            'body': 'Pre-orders for upcoming Saturday morning harvest dispatch are now open with guaranteed slot reservations.',
            'time': 'Yesterday',
            'type': 'harvest',
            'icon': '🌾'
        },
    ]

    context = {
        'account': account,
        'business_name': business_name,
        'business_subtitle': 'Central Kitchen & Restaurant Procurement Unit',
        'gstin': '27AAACS1429B1ZX · Verified B2B Buyer',
        'kpi': {
            'active_orders': 4,
            'pending_orders': 2,
            'monthly_spending': '₹1,48,250',
            'spending_budget': '₹2,00,000',
            'spending_pct': 74,
            'farming_partners': 18,
            'active_deliveries': 3,
            'total_volume_kg': '4,850 kg'
        },
        'bulk_catalog': bulk_catalog,
        'active_orders': active_orders,
        'farming_partners': farming_partners,
        'invoices': invoices,
        'notifications': notifications,
    }

    return render(request, 'bulk-buyer-dashboard.html', context)


def traceability_view(request):
    """Renders the farm-to-door batch traceability and tracking page."""
    return render(request, 'traceability.html')


def notifications_view(request):
    """Renders the unified notifications center."""
    return render(request, 'notifications.html')


@csrf_exempt
def chatbot_api_view(request):
    """Processes user queries via Google Gemini API using GEMINI_API_KEY from environment."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
        user_message = str(payload.get('message', '')).strip()
    except Exception:
        user_message = str(request.POST.get('message', '')).strip()

    if not user_message:
        return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return JsonResponse({
            'response': "Farm2Door AI is temporarily unavailable (GEMINI_API_KEY is not configured in .env)."
        })

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_instruction = (
            "You are the official Farm2Door AI Assistant. Farm2Door is an Indian agri-tech platform "
            "connecting verified farmers and Farmer Producer Organizations (FPOs) directly with consumers and "
            "commercial bulk buyers (such as hotels, restaurants, caterers, and supermarkets). "
            "Farm2Door eliminates middlemen, guarantees fair pricing to farmers, provides farm-to-door "
            "batch traceability with QR codes, and delivers fresh produce within 24 hours. "
            "Answer questions concisely, politely, and accurately. Format with clean paragraphs or bullet points."
        )

        candidate_models = [
            'gemini-flash-lite-latest',
            'gemini-3-flash-preview',
            'gemini-3.1-flash-lite-preview',
            'gemma-4-26b-a4b-it',
            'gemma-4-31b-it',
        ]
        reply_text = None
        last_error = None

        for model_name in candidate_models:
            try:
                chat = client.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=600,
                    )
                )
                response = chat.send_message(user_message)
                if response and response.text:
                    reply_text = response.text.strip()
                    break
            except Exception as model_err:
                last_error = model_err
                continue

        if not reply_text:
            if last_error:
                reply_text = f"Farm2Door Assistant is momentarily experiencing high traffic: {str(last_error)}. Please try again shortly."
            else:
                reply_text = "I'm sorry, I couldn't generate a response right now. Please ask again in a moment."

        return JsonResponse({'response': reply_text})

    except Exception as exc:
        return JsonResponse({
            'response': f"Farm2Door Assistant encountered an issue: {str(exc)}. Please try again shortly."
        }, status=200)

