from django.urls import path 
from .views import (ProductListView, 
                    ProductDetailView,
                      ProductFacetsView,
                      ProductRelatedView,
                      CategoryListView,
                      SizeChartView,
                        ProductReviewListView, 
                        ProductReviewDeleteView, 
                        ProductSuggestionsView)

urlpatterns = [
    path('', ProductListView.as_view()),
    path('categories/', CategoryListView.as_view()),
    path('suggestions/', ProductSuggestionsView.as_view()),
    path('facets/', ProductFacetsView.as_view()),
    path('size-chart/', SizeChartView.as_view()),
    path('<slug:slug>/', ProductDetailView.as_view()),
    path('<slug:slug>/related/', ProductRelatedView.as_view()),
    path('<slug:slug>/reviews/', ProductReviewListView.as_view()),
    path('<slug:slug>/reviews/mine/', ProductReviewDeleteView.as_view()),
]
