from django.contrib import admin
from api.models import User, Place, PlaceAnalysis, Review, Inquiry, PlaceImage

# 사용자 모델 등록
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_staff')

# 장소 분석 결과
@admin.register(PlaceAnalysis)
class PlaceAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_ad', 'ad_probability', 'created_at')

# 장소별 사진 여러 장을 하단에 슬롯 형태로 보여주기 위한 인라인 클래스
class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 1

# 기본 장소 정보 (인라인을 포함하여 등록)
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'created_at')  # 기존 Place 모델에서 제외된 image_url 필드는 지웠습니다.
    inlines = [PlaceImageInline]  # 이 장소를 누르면 하단에 연동된 사진들이 함께 뜹니다.

# 리뷰 관리
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'user', 'content', 'hashtags', 'rating', 'url', 'created_at')
    search_fields = ('content', 'place__name')

# 1:1 문의 관리
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'created_at')

# 독립된 사진 테이블 단독 조회용 등록
@admin.register(PlaceImage)
class PlaceImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'image_url', 'created_at')