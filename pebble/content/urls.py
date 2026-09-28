from django.urls import path

from .views import (
    PageListView, PageDetailView,
    ArticleListView, ArticleDetailView,
    SearchView,
)

urlpatterns = [
    path('pages/', PageListView.as_view()),
    path('pages/<slug:slug>/', PageDetailView.as_view()),
    path('blogs/<slug:blog_handle>/', ArticleListView.as_view()),
    path('blogs/<slug:blog_handle>/<slug:slug>/', ArticleDetailView.as_view()),
    path('search/', SearchView.as_view()),
]
