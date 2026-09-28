from django.db import models
from django.contrib.auth.models import User 
from products.models import Product, ProductVariant 


class Cart(models.Model): 
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart') 
    coupon = models.ForeignKey('coupons.Coupon', null=True, blank=True, on_delete=models.SET_NULL, related_name='carts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) 

    def __str__(self):
        return f'cart({self.user.email})'
    
    @property 
    def total(self):
        from .pricing import quote_cart
        return quote_cart(self).total

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items') 
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, related_name='cart_items', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # One row per product+variant combo in a cart
        unique_together = ('cart', 'product', 'variant')

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    @property
    def unit_price(self):
        if self.variant and self.variant.price_override is not None:
            return self.variant.price_override
        return self.product.price
    
    @property
    def line_total(self):
        return self.unit_price * self.quantity
