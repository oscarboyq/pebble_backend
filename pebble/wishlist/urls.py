from django.urls import path
from .views import WishlistView, WishlistToggleView, WishlistSlugsView

urlpatterns = [
    path('', WishlistView.as_view()),
    path('slugs/', WishlistSlugsView.as_view()),
    path('<slug:slug>/toggle/', WishlistToggleView.as_view()),
]