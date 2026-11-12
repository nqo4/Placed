from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.indexes import GinIndex

# 1. 사용자 모델
class User(AbstractUser):
    # username(아이디), password, email은 기본 포함
    phone_number = models.CharField(max_length=20, blank=True, null=True)

# 2. 장소 분석 결과 모델 (데이터 출력용)
class PlaceAnalysis(models.Model):
    name = models.CharField(max_length=100)       # 장소 이름
    content_text = models.TextField()             # 분석한 리뷰 내용

    # AI 분석 결과
    is_ad = models.BooleanField(default=False)      # 광고 여부
    # [주석 수정] 이 필드는 다른 코드(AnalyzePlaceView, SearchView)에서 "광고'일' 확률"로
    # 일관되게 사용되고 있습니다(예: 80이면 광고일 가능성이 80%). 기존 "광고가 아닐 확률"이라는
    # 주석은 실제 사용 방식과 반대라서 혼동의 원인이었습니다.
    ad_probability = models.IntegerField(verbose_name='Ad Probability', default=50)  # 광고일 확률(0~100)
    ai_summary = models.TextField()       # AI 분석 이유
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ad_probability}%)"

# 3. 장소 모델 (기본 정보)
class Place(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image_url = models.TextField(blank=True, null=True, help_text="장소 대표 이미지의 URL 주소.")
    address = models.CharField(max_length=255, blank=True)
    # [추가] 추천 시스템(해시태그/위치/업종 기반) 대응. 네이버 지역 검색 API의 category
    # 필드(예: "음식점>한식>한정식")를 그대로 저장합니다 (api/naver_miner.py, api/recommendation.py 참고).
    category = models.CharField(max_length=150, blank=True)
    # [추가 - 거리 기반 추천] 네이버 지역 검색 API 응답의 mapx/mapy(WGS84 좌표 * 10^7,
    # 별도 좌표계 변환 불필요)를 그대로 저장합니다. api/naver_miner.py의
    # _extract_coordinates(), api/recommendation.py의 similar_places_for() 참고.
    # 이 기능 추가 전에 등록된 장소는 값이 비어 있을 수 있고(null), 그 경우 거리 기반
    # 추천에서는 제외되고 키워드 유사도만으로 평가됩니다.
    latitude = models.FloatField(null=True, blank=True, help_text="WGS84 위도")
    longitude = models.FloatField(null=True, blank=True, help_text="WGS84 경도")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # [자연어 검색 보강] Elasticsearch 대신 PostgreSQL pg_trgm 확장을 사용합니다
        # (마이그레이션 0011_pg_trgm_extension, api/recommendation.py의
        # find_matching_places 참고). GIN 인덱스가 없어도 TrigramSimilarity 자체는
        # 동작하지만, 장소 수가 늘어났을 때 매번 전체 테이블을 스캔하지 않도록 이름/주소
        # 각각에 trigram GIN 인덱스를 둡니다.
        indexes = [
            GinIndex(fields=['name'], name='place_name_trgm_idx', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['address'], name='place_address_trgm_idx', opclasses=['gin_trgm_ops']),
        ]

    def __str__(self):
        return self.name

#3-1. 장소 사진 모델
class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="외부(크롤링) 이미지 URL")
    # [추가] ECR-002/SFR-004(이미지 저장 + 용량 압축) 요구사항 대응.
    # 사용자가 직접 업로드한 이미지는 압축을 거쳐 이 필드에 저장합니다. (api.image_utils 참고)
    image = models.ImageField(upload_to='places/%Y/%m/', blank=True, null=True, help_text="압축되어 저장된 이미지 파일")
    created_at = models.DateTimeField(auto_now_add=True)

# 3-2. 장소 리뷰 원본 소스 모델
class ReviewSource(models.Model):
    """
    [리뷰 소스 확장 + 평균 점수 산정] 장소 하나당 블로그/카페글 등 여러 건(최소 10건을
    목표로 함)을 개별로 모아 각각 AI로 광고 여부를 분석한 뒤, PlaceAnalysis.ad_probability는
    이 소스들의 평균으로 계산합니다(api/naver_miner.py의 _refresh_place_reviews 참고).

    사용자에게 화면으로 노출되는 Review는 이 중 평균에 가장 가까운 점수를 받은 대표 1건만
    사용합니다 - 크롤링 봇이 모은 원본 소스 전부를 리뷰 목록에 그대로 올리지 않기 위함입니다.
    리뷰를 새로 갱신할 때마다 해당 장소의 기존 소스는 삭제하고 새로 수집한 소스로 교체합니다.
    """
    SOURCE_TYPE_CHOICES = [
        ('blog', '블로그'),
        ('cafearticle', '카페글'),
    ]
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='review_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=500, blank=True, null=True)
    content_text = models.TextField()
    is_ad = models.BooleanField(default=False)
    ad_probability = models.IntegerField(default=50)
    # [추가] 오탐 매칭 완화(2단계) - 장소명이 실제로 언급되긴 했지만("알텐데 앞을 지나가는데"
    # 처럼 스치듯) 그 장소에 대한 구체적인 정보(방문 경험/메뉴/분위기/가격 등)는 없는 글을
    # 걸러내기 위한 판정 결과. AI 분석 시점(api.gemini_service.analyze_review)에 함께
    # 판단하며, 이 값이 False인 후보는 ReviewSource로 저장되지 않고 광고 확률 평균/대표
    # 리뷰 선정에서도 제외됩니다(api/naver_miner.py의 _refresh_place_reviews 참고).
    has_place_info = models.BooleanField(default=True, help_text="이 글이 장소에 대한 실질적인 정보를 담고 있는지")
    # [추가] 리뷰 필터링 - 구인공고/무관한 글/상업적 공고 판정 결과. has_place_info=False와 달리
    # is_review=False인 글은 판정 검토와 재분석 생략을 위해 저장하지만, 광고 확률 평균/대표
    # 리뷰/분위기 키워드/학습 데이터에는 반영하지 않습니다.
    EXCLUDE_REASON_CHOICES = [
        ('job_posting', '구인공고'),
        ('unrelated', '무관한 글'),
        ('other_notice', '기타 공고'),
    ]
    is_review = models.BooleanField(default=True, help_text="이 글이 실제 방문/이용 후기인지")
    exclude_reason = models.CharField(max_length=20, choices=EXCLUDE_REASON_CHOICES, null=True, blank=True)
    # [추가] AI 호출 실패로 기본값(50%)이 저장된 글. 재사용하지 않고 다음 수집 때 다시 분석하며,
    # 다른 글에 정상 판정이 있으면 광고 확률 평균/대표 리뷰에서도 제외합니다.
    analysis_failed = models.BooleanField(default=False, help_text="AI 분석 실패로 기본값이 저장된 글인지")
    # [추가] 글쓴이가 평가한 후기 키워드와 근거 [{"keyword": ..., "evidence": ...}]
    # (api/keyword_taxonomy.py의 REVIEW_TOPIC_KEYWORDS). null은 아직 키워드를 뽑지 않은 글이라
    # 다음 수집 때 다시 분석하고, 빈 배열은 분석했지만 해당 키워드가 없는 글입니다.
    topic_keywords = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # [추가] 자체 학습 데이터셋 구축(1단계) - AI가 예측한 is_ad/ad_probability와는 별개로,
    # 관리자가 admin에서 실제로 확인/확정한 정답만 여기 남깁니다. is_ad_verified=True인
    # 항목만 "검증된 레이블"로 보고, api/management/commands/export_training_data.py가
    # 이 값들을 모아 학습용 데이터셋 파일로 내보냅니다.
    is_ad_verified = models.BooleanField(default=False, help_text="사람이 광고 여부를 검토/확정했는지")
    verified_is_ad = models.BooleanField(null=True, blank=True, default=None, help_text="사람이 확정한 광고 여부 (미검토면 None)")
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_review_sources'
    )

    class Meta:
        indexes = [models.Index(fields=['place'])]

    def __str__(self):
        return f"{self.place.name} - {self.source_type} - {self.title[:20]}"


# 3-3. 장소 키워드 모델 (해시태그를 대체하는, 장소를 구분하기 위한 통제된 키워드)
class PlaceKeyword(models.Model):
    """
    [키워드 기반 장소 구분] 블로그 본문에서 정규식으로 뽑아낸 해시태그(상호명/무관한 단어가
    섞임)를 대신해, 장소를 명확하게 구분할 수 있는 키워드만 담습니다. 자세한 생성 규칙은
    api/keyword_taxonomy.py 상단 설명과 api/naver_miner.py 참고.

    - location(위치): 주소 기반, 결정적 계산 (예: "대전 유성구", "궁동")
    - category(종류): Place.category 기반, 결정적 계산 (예: "음식점", "한식", "이자카야")
    - mood(분위기/특징): keyword_taxonomy.MOOD_KEYWORDS 안에서만 AI가 고른 값 (예: "데이트")

    추천 시스템(api/recommendation.py)이 이 테이블을 읽어 장소 간 유사도를 계산합니다.
    """
    KEYWORD_TYPE_CHOICES = [
        ('location', '위치'),
        ('category', '종류'),
        ('mood', '분위기/특징'),
    ]
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=50)
    keyword_type = models.CharField(max_length=20, choices=KEYWORD_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    # [추가] 자체 학습 데이터셋 구축(1단계) - 사람이 이 키워드가 실제로 맞는지 확인한 결과.
    # location/category는 결정적 계산이라 보통 검증이 필요 없지만, mood(분위기)는 AI가 고른
    # 값이라 여기서 확인/오답 표시를 남겨두면 향후 자체 분류기 학습의 레이블로 쓸 수 있습니다
    # (api/management/commands/export_training_data.py 참고).
    verified = models.BooleanField(null=True, blank=True, default=None, help_text="사람이 확인한 결과 (True=맞음, False=틀림, None=미검토)")
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['place']), models.Index(fields=['keyword'])]

    def __str__(self):
        return f"{self.place.name} - [{self.keyword_type}] {self.keyword}"


# 4. 리뷰 모델
class Review(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    content = models.TextField()
    hashtags = models.TextField(blank=True, null=True, help_text="해시태그들을 저장합니다.")
    rating = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.place.name} - {self.user.username}"

# 5-1. 검색 기록 모델 (SFR-005/DAR-002: 로그인 사용자 기반 추천을 위한 데이터)
class SearchLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_logs')
    keyword = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f"{self.user.username}: {self.keyword}"


# 5-2. 장소 조회(선택) 기록 모델 (SFR-005/SFR-007/DAR-002: 추천 시스템을 위한 행동 데이터)
class PlaceViewLog(models.Model):
    """
    [추가] 사용자가 검색 결과 등에서 실제로 눌러서 상세 페이지를 연(=선택한) 장소를
    기록합니다. 단순히 검색창에 입력한 키워드(SearchLog)보다 더 강한 취향 신호로 보고
    추천 스코어링에서 더 높은 가중치를 둡니다(api/recommendation.py 참고).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='place_views')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='view_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f"{self.user.username} -> {self.place.name}"


# 5. 1:1 문의 모델
class Inquiry(models.Model):
    CATEGORY_CHOICES = [
        ('account', '계정 문의'),
        ('service', '서비스 이용'),
        ('etc', '기타'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inquiries')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='etc')
    message = models.TextField()
    # 관리자 화면에서 다는 답변. 답변 전에는 빈 값입니다.
    answer = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.category}] {self.user.username} - {self.message[:20]}"