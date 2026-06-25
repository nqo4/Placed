from django.urls import path
from .views import (
    CheckIDView, LoginView, SignupView,
    CreateInquiryView, MyInquiriesView, InquiryDetailView,
    PlaceDetailView, PlaceReviewsView, CreateReviewView, MyReviewsView,
    SearchView, AnalyzePlaceView, AISearchView, ElasticSearchPlaceView,
)

urlpatterns = [
    # Users
    path('users/check-id/', CheckIDView.as_view(), name='check-id'),
    path('users/login/', LoginView.as_view(), name='login'),
    path('users/signup/', SignupView.as_view(), name='signup'),

    # Inquiries
    path('inquiries/create/', CreateInquiryView.as_view(), name='create-inquiry'),
    path('inquiries/mine/', MyInquiriesView.as_view(), name='my-inquiries'),
    path('inquiries/<int:pk>/', InquiryDetailView.as_view(), name='inquiry-detail'),

    # Places & Reviews
    path('places/<int:pk>/', PlaceDetailView.as_view(), name='place-detail'),
    path('reviews/place/<int:place_id>/', PlaceReviewsView.as_view(), name='place-reviews'),
    path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    path('reviews/mine/', MyReviewsView.as_view(), name='my-reviews'),

    # Search
    path('search/', SearchView.as_view(), name='search'),
    path('search/ai/', AISearchView.as_view(), name='search-ai'),

    # Legacy / Analysis
    path('analyze/', AnalyzePlaceView.as_view(), name='analyze'),

    #Elasticsearch
    path('search/elastic/', ElasticSearchPlaceView.as_view(), name='elastic-search'),
]