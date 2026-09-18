import json

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth.hashers import make_password

from .models import Account, Product


class CoreViewsTests(TestCase):
    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_login_page(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_login_redirects_using_stored_account_role(self):
        Account.objects.create(
            email='farmer@example.com',
            phone='9876543210',
            role='farmer',
            password_hash=make_password('secret123'),
        )
        response = self.client.post(reverse('login'), {
            'email': 'farmer@example.com',
            'phone': '9876543210',
            'password': 'secret123',
            'role': 'consumer',
        })
        self.assertRedirects(response, reverse('farmer_dashboard'))

    def test_farmer_registration_redirects_to_farmer_dashboard(self):
        response = self.client.post(
            reverse('register'),
            data='{"name":"Riya","email":"riya@example.com","phone":"9876543219","password":"secret123","role":"farmer"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect'], reverse('farmer_dashboard'))

    def test_signin_page(self):
        response = self.client.get(reverse('signin'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'signin.html')

    def test_marketplace_page(self):
        response = self.client.get(reverse('marketplace'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace.html')

    def test_cart_sync_keeps_product_image_urls(self):
        response = self.client.post(
            reverse('cart_sync'),
            data=json.dumps({
                'items': [{
                    'id': 1,
                    'name': 'Tomato',
                    'unit': 'kg',
                    'farmer': 'Ramesh Kisan FPO',
                    'price': '25',
                    'cat': 'veg',
                    'quantity': 2,
                    'img': 'https://example.com/tomato.jpg',
                }]
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.session['cart_items']['str(1)']['img'],
            'https://example.com/tomato.jpg',
        )

    def test_checkout_page(self):
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'checkout.html')

    def test_farmer_dashboard_page(self):
        account = Account.objects.create(
            email='farmer@example.com',
            phone='9876543210',
            role='farmer',
            password_hash='unused',
        )
        session = self.client.session
        session['account_id'] = account.pk
        session.save()
        self.client.cookies['sessionid'] = session.session_key
        response = self.client.get(reverse('farmer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'farmer-dashboard.html')

    def test_non_farmer_is_redirected_from_farmer_dashboard(self):
        account = Account.objects.create(
            email='consumer@example.com',
            phone='9876543211',
            role='consumer',
            password_hash='unused',
        )
        session = self.client.session
        session['account_id'] = account.pk
        session.save()
        self.client.cookies['sessionid'] = session.session_key
        response = self.client.get(reverse('farmer_dashboard'))
        self.assertRedirects(response, reverse('marketplace'))

    def test_farmer_can_create_listing(self):
        account = Account.objects.create(
            email='farmer@example.com',
            phone='9876543210',
            name='Ramesh Patil',
            role='farmer',
            password_hash='unused',
        )
        session = self.client.session
        session['account_id'] = account.pk
        session.save()
        response = self.client.post(
            reverse('farmer_listing_create'),
            data='{"name":"Tomato","quantity":50,"price":20}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Product.objects.filter(name='Tomato', farmer_name='Ramesh Patil').exists())

    def test_delivery_dashboard_page(self):
        response = self.client.get(reverse('delivery_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'delivery-dashboard.html')

    def test_admin_dashboard_page(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin-dashboard.html')

    def test_traceability_page(self):
        response = self.client.get(reverse('traceability'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'traceability.html')

    def test_notifications_page(self):
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'notifications.html')

    def test_bulk_buyer_dashboard_page(self):
        response = self.client.get(reverse('bulk_buyer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bulk-buyer-dashboard.html')
        self.assertContains(response, 'Sharma Restaurant')
        self.assertContains(response, 'Source Fresh Produce for Your Business')
        self.assertContains(response, 'Your Bulk Order')
        self.assertContains(response, 'AI Procurement Insights')

    def test_bulk_role_routing(self):
        from core.views import _dashboard_for_role
        self.assertEqual(_dashboard_for_role('bulk'), 'bulk_buyer_dashboard')
        self.assertEqual(_dashboard_for_role('farmer'), 'farmer_dashboard')
        self.assertEqual(_dashboard_for_role('consumer'), 'marketplace')
        self.assertEqual(_dashboard_for_role('delivery'), 'delivery_dashboard')
        self.assertEqual(_dashboard_for_role('admin'), 'admin_dashboard')

    def test_chatbot_api_endpoint(self):
        response = self.client.post(
            reverse('chatbot_api'),
            data=json.dumps({'message': 'What is Farm2Door?'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('response', data)
        self.assertTrue(len(data['response']) > 0)

    def test_chatbot_voice_input_elements_in_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="f2dChatMicBtn"')
        self.assertContains(response, 'id="f2dChatLangBtn"')
        self.assertContains(response, 'id="f2dVoiceListeningBar"')
        self.assertContains(response, 'window.SpeechRecognition || window.webkitSpeechRecognition')
        self.assertContains(response, 'en-IN')
        self.assertContains(response, 'hi-IN')

    def test_chatbot_conversation_persistence_elements_in_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="f2dChatClearBtn"')
        self.assertContains(response, 'f2d_chatbot_history')
        self.assertContains(response, 'saveMessageToHistory')
        self.assertContains(response, 'loadHistory')
        self.assertContains(response, 'clearHistory')


