from django.urls import path 
from .views import HomePageView, NewsletterSubscribeView

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('newsletter/', NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
]
