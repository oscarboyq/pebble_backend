from django.urls import path 
from .views import CartView, CartItemAddView, CartItemUpdateView, CartClearView, CartCouponView, CartBundleAddView

urlpatterns = [
    path('', CartView.as_view()),
    path('items/', CartItemAddView.as_view()),
    path('bundles/', CartBundleAddView.as_view()),
    path('items/<int:item_id>/', CartItemUpdateView.as_view()),
    path('clear/', CartClearView.as_view()),
    path('coupon/', CartCouponView.as_view()),
]
