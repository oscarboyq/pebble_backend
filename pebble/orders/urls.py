from django.urls import path
from .views import PlaceOrderView, OrderListView, OrderDetailView

urlpatterns = [
    path('', OrderListView.as_view()),
    path('place/', PlaceOrderView.as_view()),
    path('<int:order_id>/', OrderDetailView.as_view()),
]