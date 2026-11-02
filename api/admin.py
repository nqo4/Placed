from django.contrib import admin
from django.utils import timezone
from api.models import (
    User, Place, PlaceAnalysis, Review, ReviewSource, PlaceKeyword,
    Inquiry, PlaceImage, SearchLog, PlaceViewLog
)

# 사용자 모델 등록
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_staff')

# 장소 분석 결과
@admin.register(PlaceAnalysis)
class PlaceAnalysisAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_ad', 'ad_probability', 'created_at')

# 장소별 사진 여러 장을 하단에 슬롯 형태로 보여주기 위한 인라인 클래스
class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 1

# 기본 장소 정보 (인라인을 포함하여 등록)
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    # [수정] 추천 시스템용 category 필드를 목록에 추가했습니다.
    list_display = ('id', 'name', 'category', 'address', 'created_at')
    inlines = [PlaceImageInline]  # 이 장소를 누르면 하단에 연동된 사진들이 함께 뜹니다.

# 리뷰 관리
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'user', 'content', 'hashtags', 'rating', 'created_at')

# [추가] 리뷰 원본 소스 관리 - 장소 하나당 모은 블로그/카페글 여러 건과 개별 점수를
# 확인/디버깅할 수 있도록 등록 (화면에는 대표 리뷰 1건만 노출되므로 전체 소스는 여기서 확인)
# [추가: 자체 학습 데이터셋 구축 1단계] 목록에서 여러 건을 선택해 아래 액션으로 광고 여부를
# "정답"으로 확정하면 is_ad_verified/verified_is_ad에 기록됩니다. 이렇게 검증된 레이블만
# api/management/commands/export_training_data.py가 학습용 데이터셋으로 내보냅니다.
@admin.register(ReviewSource)
class ReviewSourceAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'place', 'source_type', 'title', 'is_ad', 'ad_probability',
        'has_place_info', 'is_ad_verified', 'verified_is_ad', 'created_at',
    )
    list_filter = ('source_type', 'is_ad', 'has_place_info', 'is_ad_verified', 'verified_is_ad')
    search_fields = ('place__name', 'title')
    actions = ['mark_verified_ad', 'mark_verified_not_ad']

    @admin.action(description='[검증] 선택 항목을 "광고 맞음"으로 확정')
    def mark_verified_ad(self, request, queryset):
        updated = queryset.update(
            is_ad_verified=True, verified_is_ad=True,
            verified_at=timezone.now(), verified_by=request.user,
        )
        self.message_user(request, f"{updated}건을 '광고 맞음'으로 확정했습니다.")

    @admin.action(description='[검증] 선택 항목을 "광고 아님"으로 확정')
    def mark_verified_not_ad(self, request, queryset):
        updated = queryset.update(
            is_ad_verified=True, verified_is_ad=False,
            verified_at=timezone.now(), verified_by=request.user,
        )
        self.message_user(request, f"{updated}건을 '광고 아님'으로 확정했습니다.")

# [추가] 장소 키워드 관리 - 해시태그를 대신하는, 장소를 구분하기 위한 통제된 키워드
# (위치/종류는 결정적 계산, 분위기는 AI가 통제된 목록에서만 고름 - api/keyword_taxonomy.py 참고)
# [추가: 자체 학습 데이터셋 구축 1단계] 특히 mood 키워드가 실제로 맞는지 아래 액션으로
# 확인/오답 표시를 남겨두면, 향후 자체 분위기 키워드 분류기를 학습할 때 레이블로 씁니다.
@admin.register(PlaceKeyword)
class PlaceKeywordAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'keyword_type', 'keyword', 'verified', 'created_at')
    list_filter = ('keyword_type', 'verified')
    search_fields = ('place__name', 'keyword')
    actions = ['mark_verified_correct', 'mark_verified_incorrect']

    @admin.action(description='[검증] 선택 항목을 "맞음"으로 확정')
    def mark_verified_correct(self, request, queryset):
        updated = queryset.update(verified=True, verified_at=timezone.now())
        self.message_user(request, f"{updated}건을 '맞음'으로 확정했습니다.")

    @admin.action(description='[검증] 선택 항목을 "틀림"으로 확정')
    def mark_verified_incorrect(self, request, queryset):
        updated = queryset.update(verified=False, verified_at=timezone.now())
        self.message_user(request, f"{updated}건을 '틀림'으로 확정했습니다.")

# 1:1 문의 관리
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'created_at')

# 독립된 사진 테이블 단독 조회용 등록
@admin.register(PlaceImage)
class PlaceImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'image_url', 'image', 'created_at')

# [추가] 검색 기록 관리 (SFR-005/DAR-002)
@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'keyword', 'created_at')
    list_filter = ('user',)

# [추가] 장소 조회(선택) 기록 관리 (SFR-005/SFR-007/DAR-002: 추천 시스템 행동 데이터)
@admin.register(PlaceViewLog)
class PlaceViewLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'place', 'created_at')
    list_filter = ('user',)