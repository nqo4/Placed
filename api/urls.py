from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CheckIDView, LoginView, SignupView,
    FindIdView, PasswordResetView, DeleteAccountView,
    CreateInquiryView, MyInquiriesView, InquiryDetailView,
    PlaceDetailView, SimilarPlacesView, PlaceReviewsView, CreateReviewView, MyReviewsView,
    SearchView, RecommendView, DailyRecommendView, UploadPlaceImageView, AnalyzePlaceView, AISearchView,
    PlaceKeywordSearchView, AdminUserListView, AdminPlaceListView, AdminAnalysisListView,
    AdminReviewListView, AdminInquiryListView,
)

urlpatterns = [
    # Users
    path('users/check-id/', CheckIDView.as_view(), name='check-id'),
    path('users/login/', LoginView.as_view(), name='login'),
    path('users/login/refresh/', TokenRefreshView.as_view(), name='login-refresh'),
    path('users/signup/', SignupView.as_view(), name='signup'),
    # [추가] SFR-001: 아이디 찾기 / 비밀번호 재설정 / 회원 탈퇴
    path('users/find-id/', FindIdView.as_view(), name='find-id'),
    path('users/password-reset/', PasswordResetView.as_view(), name='password-reset'),
    path('users/delete-account/', DeleteAccountView.as_view(), name='delete-account'),

    # Inquiries
    path('inquiries/create/', CreateInquiryView.as_view(), name='create-inquiry'),
    path('inquiries/mine/', MyInquiriesView.as_view(), name='my-inquiries'),
    path('inquiries/<int:pk>/', InquiryDetailView.as_view(), name='inquiry-detail'),

    # Places & Reviews
    path('places/<int:pk>/', PlaceDetailView.as_view(), name='place-detail'),
    # [추가] 장소 상세 - 비슷하거나 가까운 매장 추천 (api/recommendation.py의 similar_places_for)
    path('places/<int:pk>/similar/', SimilarPlacesView.as_view(), name='place-similar'),
    path('reviews/place/<int:place_id>/', PlaceReviewsView.as_view(), name='place-reviews'),
    path('reviews/create/', CreateReviewView.as_view(), name='create-review'),
    path('reviews/mine/', MyReviewsView.as_view(), name='my-reviews'),
    # [추가] ECR-002/SFR-004: 장소 이미지 업로드(압축 저장)
    path('places/images/upload/', UploadPlaceImageView.as_view(), name='place-image-upload'),

    # Search
    path('search/', SearchView.as_view(), name='search'),
    path('search/ai/', AISearchView.as_view(), name='search-ai'),
    # [추가] SFR-005/DAR-002: 검색 기록 기반 개인화 추천
    path('search/recommend/', RecommendView.as_view(), name='search-recommend'),
    # [추가] 오늘의 추천 장소 - 로그인 첫 화면용, 식당/카페/술집 각 1곳씩
    path('search/recommend/daily/', DailyRecommendView.as_view(), name='search-recommend-daily'),

    # Legacy / Analysis
    path('analyze/', AnalyzePlaceView.as_view(), name='analyze'),

    # 프론트엔드 호환 경로 (Elasticsearch -> pg_trgm 대체)
    path('search/elastic/', PlaceKeywordSearchView.as_view(), name='elastic-search'),

    # Admin
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/places/', AdminPlaceListView.as_view(), name='admin-places'),
    path('admin/analysis/', AdminAnalysisListView.as_view(), name='admin-analysis'),
    path('admin/reviews/', AdminReviewListView.as_view(), name='admin-reviews'),
    path('admin/inquiries/', AdminInquiryListView.as_view(), name='admin-inquiries'),
]
