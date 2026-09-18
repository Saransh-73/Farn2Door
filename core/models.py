import uuid

from django.db import models


def make_registered_id():
	return f'F2D-{uuid.uuid4().hex[:10].upper()}'


class Account(models.Model):
	ROLE_CHOICES = [
		('farmer', 'Farmer / FPO'),
		('consumer', 'Consumer'),
		('bulk', 'Bulk Buyer'),
		('delivery', 'Delivery Partner'),
		('admin', 'Admin'),
	]

	registered_id = models.CharField(max_length=14, unique=True, default=make_registered_id, editable=False)
	name = models.CharField(max_length=160, blank=True, default='')
	email = models.EmailField(unique=True)
	phone = models.CharField(max_length=10)
	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='consumer')
	password_hash = models.CharField(max_length=128)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.email} ({self.registered_id})'


class Product(models.Model):
	name = models.CharField(max_length=160)
	category = models.CharField(max_length=80)
	description = models.TextField(blank=True)
	unit = models.CharField(max_length=40, default='kg')
	price = models.DecimalField(max_digits=10, decimal_places=2)
	stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	farmer_name = models.CharField(max_length=160)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return self.name


class Order(models.Model):
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('confirmed', 'Confirmed'),
		('delivered', 'Delivered'),
		('cancelled', 'Cancelled'),
	]

	customer_name = models.CharField(max_length=160)
	customer_phone = models.CharField(max_length=30)
	delivery_address = models.TextField()
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'Order #{self.pk}'


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
	product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
	quantity = models.DecimalField(max_digits=10, decimal_places=2)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2)

	@property
	def line_total(self):
		return self.quantity * self.unit_price
