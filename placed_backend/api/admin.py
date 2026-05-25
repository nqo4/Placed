from django.contrib import admin
from .models import User, Place, PlaceAnalysis, Review, Inquiry

# 사용자 모델 등록
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_staff')

# 장소 분석 결과
@admin.register(PlaceAnalysis)
class PlaceAnalysisAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_ad', 'ad_probability', 'created_at')

# 기본 장소 정보
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'image_url', 'created_at')

# 리뷰 관리
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'user', 'content', 'hashtags', 'rating', 'created_at')
# 1:1 문의 관리
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'created_at')