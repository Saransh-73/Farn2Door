from django.test import SimpleTestCase
from django.urls import reverse


class CoreViewsTests(SimpleTestCase):
    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_login_page(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_signin_page(self):
        response = self.client.get(reverse('signin'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'signin.html')

    def test_marketplace_page(self):
        response = self.client.get(reverse('marketplace'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace.html')

    def test_checkout_page(self):
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'checkout.html')

    def test_farmer_dashboard_page(self):
        response = self.client.get(reverse('farmer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'farmer-dashboard.html')

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
