"""
[키워드 기반 장소 구분] 해시태그(블로그 본문에서 정규식으로 뽑아낸 "#단어") 대신, 장소를
명확하게 구분할 수 있는 키워드만 다루기 위한 통제된 어휘집(taxonomy)입니다.

기존 방식의 문제: Review.hashtags는 블로그 글의 "#상호명", "#오늘의날씨" 같은 임의의
해시태그를 정규식(`#[가-힣a-zA-Z0-9_]+`)으로 그대로 긁어온 것이라, 장소를 구분하는 데
쓰기엔 노이즈(상호명, 무관한 단어)가 많이 섞여 있었습니다.

대신 PlaceKeyword(api/models.py)는 아래 세 종류로만 구성되고, 각각 생성 방식이 다릅니다.

1. location(위치): 주소에서 뽑아낸 시/구/동 등 - api/naver_miner.py가 결정적으로 계산
   (AI 미사용, 항상 정확함).
2. category(종류): 네이버 지역 검색이 이미 분류해 둔 업종(Place.category, 예:
   "음식점>한식>한정식")을 그대로 토큰화 - 마찬가지로 결정적 계산, AI 미사용.
   (이자카야/와인바/칵테일바/주점 같은 세부 업종도 네이버가 이미 이렇게 분류해 두는
   경우가 많아 별도 AI 판단 없이도 상당수 커버됩니다.)
3. mood(분위기/특징): 아래 MOOD_KEYWORDS 목록 안에서만 고르도록 AI에게 강제합니다. 리뷰
   본문(블로그/카페글)을 분석해 어울리는 항목만 선택하게 하고, 목록에 없는 단어가 응답에
   섞여 와도 서버 쪽에서 한 번 더 걸러냅니다(api/naver_miner.py의 _extract_mood_keywords
   참고). "분위기 좋은", "디저트카페" 처럼 공식 업종 분류에는 없는 감성/스타일 정보는 이
   경로로만 채워집니다.

새 카테고리를 추가하고 싶으면 이 목록에 단어를 추가하기만 하면 됩니다 - 코드 다른 곳은
건드릴 필요 없습니다.
"""

# 분위기/특징 키워드 (업종과 무관하게 여러 개 붙을 수 있음). AI는 이 목록 안에서만 고릅니다.
MOOD_KEYWORDS = [
    "분위기좋은", "데이트", "혼밥", "가성비", "인스타감성", "조용한",
    "단체모임", "웨이팅있음", "뷰맛집", "반려동물동반", "룸있음", "야외석",
    "가족모임", "회식", "24시간", "주차편리", "디저트맛집", "브런치",
]

MAX_MOOD_KEYWORDS_PER_PLACE = 5


# [오늘의 추천 장소] 로그인 첫 화면에 식당/카페/술집 각 1곳씩 보여주기 위해, Place.category
# (네이버 업종 분류, category_tokens()로 토큰화됨) 토큰을 3개 그룹 중 하나로 묶습니다.
# 네이버 지역 검색은 술집을 "음식점>이자카야", "음식점>호프,요리주점"처럼 음식점 하위로
# 분류하는 경우가 많아, PLACE_TYPE_ORDER는 술집을 가장 먼저 검사합니다 - 그렇지 않으면
# "음식점" 토큰 때문에 전부 식당으로 분류돼 버립니다.
PLACE_TYPE_ORDER = ['bar', 'cafe', 'restaurant']

PLACE_TYPE_LABELS = {
    'restaurant': '식당',
    'cafe': '카페',
    'bar': '술집',
}

PLACE_TYPE_CATEGORY_TOKENS = {
    'bar': {'이자카야', '와인바', '칵테일바', '주점', '호프', '포차', 'BAR', '바(BAR)', '요리주점', '술집', '맥주'},
    'cafe': {'카페', '디저트', '베이커리', '제과', '커피전문점'},
    'restaurant': {'음식점', '한식', '중식', '일식', '양식', '분식', '고깃집', '뷔페', '해산물', '치킨'},
}


def classify_place_type(place_category_tokens):
    """
    장소의 category 토큰 집합(category_tokens(place.category))을 보고 'restaurant'/'cafe'/
    'bar' 중 하나로 분류합니다. 여러 그룹의 토큰이 섞여 있으면 PLACE_TYPE_ORDER 순서대로
    먼저 매칭되는 그룹을 사용합니다. 어디에도 안 맞으면 None을 반환합니다.
    """
    for place_type in PLACE_TYPE_ORDER:
        if place_category_tokens & PLACE_TYPE_CATEGORY_TOKENS[place_type]:
            return place_type
    return None
