"""
[SFR-005/SFR-007/DAR-002 고도화] 로그인 사용자의 행동 패턴(검색 키워드 + 실제로 선택/조회한
장소)을 누적해, 키워드(위치/종류/분위기)가 비슷한 장소를 추천하기 위한 헬퍼 모음입니다.

원 요구사항(SFR-007)이 명시한 Neural CF 모델은 별도의 학습 파이프라인/데이터셋이 필요해
이번 저장소 범위를 벗어납니다(REPORT에 별도 명시). 대신 지금 쌓이는 행동 데이터만으로
동작하는 컨텐츠 기반(content-based) 베이스라인으로 다음 두 가지 신호를 함께 사용합니다:
- SearchLog: 사용자가 검색창에 입력한 키워드 (약한 신호)
- PlaceViewLog: 사용자가 실제로 눌러서 상세 페이지를 연 장소 (검색만 한 것보다 강한 신호 →
  가중치를 더 높게 둡니다)

[키워드 기반 장소 구분] 각 장소의 "내용"은 PlaceKeyword(api/models.py)로 표현합니다.
예전에는 리뷰 본문에서 정규식으로 뽑아낸 해시태그(상호명 등 노이즈가 섞임)를 사용했지만,
지금은 위치/업종은 결정적으로 계산하고 분위기는 통제된 어휘집 안에서만 AI가 고르는
PlaceKeyword로 대체했습니다 - 생성 규칙은 api/keyword_taxonomy.py, api/naver_miner.py 참고.

region_hint()/category_tokens()는 여기서는 더 이상 스코어링에 쓰이지 않지만(그 역할을
PlaceKeyword가 대신함), api/naver_miner.py가 PlaceKeyword의 location/category 값을 만들 때
그대로 재사용하는 공용 유틸리티라 이 모듈에 남겨둡니다.

[오늘의 추천 장소] recommend_places_for_user()(상위 10건, 검색+조회 통합)와는 별개로,
daily_recommended_places()는 로그인 첫 화면용으로 식당/카페/술집 각 1곳씩만 고릅니다.
오직 검색 기록만 보고, "1) 주로 검색한 동네 2) 주로 검색한 연관 키워드" 순서로 우선순위를
매깁니다 - api/views.py의 DailyRecommendView 참고.
"""
import math
import re
from collections import Counter

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from .keyword_taxonomy import PLACE_TYPE_ORDER, classify_place_type
from .models import Place, PlaceKeyword, PlaceViewLog, SearchLog

# [PostgreSQL pg_trgm 기반 오타/유사 표기 허용] Elasticsearch 없이, 이미 쓰고 있는
# PostgreSQL의 pg_trgm 확장(마이그레이션 0011_pg_trgm_extension 참고)만으로 "자연어
# 검색"에 가까운 체감을 주기 위한 임계값입니다. 장소명/주소가 검색 토큰과 글자 단위로
# 이 값 이상 비슷하면(0~1, 높을수록 엄격) 정확히 포함되지 않아도 매칭으로 인정합니다
# (예: "스타벅스"를 "스타백스"로 잘못 입력해도 찾아줌). 너무 낮추면 무관한 결과가 섞이고
# 너무 높이면 오타 허용 효과가 거의 없어지므로, 필요하면 이 값만 조정하면 됩니다.
TRIGRAM_SIMILARITY_THRESHOLD = 0.3

VIEW_WEIGHT = 3          # 실제로 선택(조회)한 장소 1건의 가중치
SEARCH_WEIGHT = 1        # 검색 키워드 1건의 가중치
RECENT_SEARCH_LIMIT = 30
RECENT_VIEW_LIMIT = 30
CANDIDATE_LIMIT = 300    # 추천 후보로 검토할 장소 상한(전체 장소가 매우 많아질 때 성능 보호)
TOP_N = 10


def place_keyword_set(place):
    """장소의 키워드(위치/종류/분위기)를 모두 모아 중복 없는 문자열 집합으로 반환합니다."""
    return set(place.keywords.values_list('keyword', flat=True))


def find_matching_places(keyword):
    """
    [키워드 인식 검색 + 오타/유사 표기 허용] 검색어를 공백 기준으로 토큰화해서, 각
    토큰이 장소명/주소에 그대로 포함되는지, PlaceKeyword(위치/종류/분위기)에 있는지
    확인합니다. 추가로 PostgreSQL pg_trgm 확장(TrigramSimilarity)으로 장소명/주소가
    토큰과 글자 단위로 TRIGRAM_SIMILARITY_THRESHOLD 이상 비슷하면, 정확히 포함되지
    않아도(오타, 띄어쓰기 차이, 부분 표기 등) 매칭으로 인정합니다. Elasticsearch 없이
    이미 쓰는 PostgreSQL만으로 자연어 검색에 가까운 체감을 주기 위한 보강입니다.

    api/views.py의 SearchView가 실제 검색 결과를 만들 때 쓰는 것과 동일한 함수이고,
    api/management/commands/export_recommendation_dataset.py가 "이 검색으로 어떤
    장소들이 노출됐는지"를 재구성해 추천용 데이터셋의 약한 신호(검색 매칭)를 만들 때도
    재사용합니다 - 두 곳의 매칭 기준이 어긋나지 않도록 로직을 한 곳에 모아둡니다.

    토큰마다 별도로 annotate()+filter()를 체이닝해 "각 토큰이 (이름 또는 주소에 포함,
    또는 그 장소의 키워드 중 하나와 일치, 또는 이름/주소와 글자 단위로 충분히 비슷함)"에
    매칭되면 통과하도록 합니다. 토큰 여러 개가 전부 만족돼야 하지만, 같은 매칭 한 행이
    모든 토큰을 동시에 만족할 필요는 없습니다(Django에서 다중 값 관계에 여러 filter()를
    체이닝하면 각각 독립적인 조인으로 평가되기 때문입니다). 토큰마다 annotate alias를
    다르게(예: _name_sim_0, _addr_sim_0) 둬서 토큰별 유사도 계산이 서로 덮어쓰지 않게
    합니다.
    """
    tokens = [t for t in keyword.split() if t]
    if not tokens:
        return Place.objects.none()

    places_qs = Place.objects.all()
    for i, token in enumerate(tokens):
        name_sim = f'_name_sim_{i}'
        addr_sim = f'_addr_sim_{i}'
        places_qs = places_qs.annotate(**{
            name_sim: TrigramSimilarity('name', token),
            addr_sim: TrigramSimilarity('address', token),
        }).filter(
            Q(name__icontains=token)
            | Q(address__icontains=token)
            | Q(keywords__keyword__icontains=token)
            | Q(**{f'{name_sim}__gte': TRIGRAM_SIMILARITY_THRESHOLD})
            | Q(**{f'{addr_sim}__gte': TRIGRAM_SIMILARITY_THRESHOLD})
        )
    return places_qs.distinct()


def region_hint(address):
    """
    주소 앞부분 2토큰(예: "대전 유성구")을 지역 단위로 사용합니다. 토큰이 1개뿐이면 그것만
    사용. api/naver_miner.py가 PlaceKeyword(location)를 만들 때 재사용하는 공용 유틸리티.
    """
    if not address:
        return ''
    tokens = address.split()
    if len(tokens) >= 2:
        return ' '.join(tokens[:2])
    return tokens[0] if tokens else ''


def neighborhood_hint(address):
    """
    주소 3번째 토큰(예: "대전 유성구 궁동"의 "궁동")을 동/읍/면 단위 힌트로 사용합니다.
    숫자가 섞이거나 도로명(~로/~길)으로 끝나면 동 단위가 아니라고 보고 빈 문자열을
    반환합니다(신호 없음). region_hint()보다 더 구체적인 위치 신호입니다.

    api/naver_miner.py가 PlaceKeyword(location)를 만들 때, 그리고 리뷰 소스를 모을 때
    "이름은 같지만 실제로는 다른 지점/장소"를 걸러내는 가장 강한 신호로 재사용하는 공용
    유틸리티입니다 - 같은 상호가 같은 시/구 안에 여러 지점을 낼 수 있어(예: 카페
    프랜차이즈), region_hint() 하나만으로는 지점을 구분하지 못합니다.
    """
    if not address:
        return ''
    tokens = address.split()
    if len(tokens) < 3:
        return ''
    third_token = tokens[2]
    if not third_token or re.search(r'\d', third_token) or third_token.endswith(('로', '길')):
        return ''
    return third_token


def category_tokens(category):
    """
    "음식점>한식>한정식" 같은 계층형 카테고리 문자열을 토큰 집합으로 쪼갭니다.
    api/naver_miner.py가 PlaceKeyword(category)를 만들 때 재사용하는 공용 유틸리티.
    """
    if not category:
        return set()
    return {token.strip() for token in category.split('>') if token.strip()}


def build_preference_profile(user):
    """
    최근 검색 키워드 + 최근 조회(선택)한 장소들로부터 키워드 선호도(Counter)를 만듭니다.
    조회한 장소가 있으면 그 장소들의 PlaceKeyword(위치/종류/분위기)에 VIEW_WEIGHT를 줍니다.

    반환값: (keyword_scores, recent_keywords, recent_view_ids)
    """
    recent_keywords = list(
        SearchLog.objects.filter(user=user).order_by('-created_at')
        .values_list('keyword', flat=True)[:RECENT_SEARCH_LIMIT]
    )
    recent_view_ids = list(
        PlaceViewLog.objects.filter(user=user).order_by('-created_at')
        .values_list('place_id', flat=True)[:RECENT_VIEW_LIMIT]
    )
    viewed_places_by_id = {p.id: p for p in Place.objects.filter(id__in=recent_view_ids)}

    keyword_scores = Counter()
    for place_id in recent_view_ids:
        place = viewed_places_by_id.get(place_id)
        if not place:
            continue  # 조회 이후 삭제된 장소일 수 있음
        for keyword in place_keyword_set(place):
            keyword_scores[keyword] += VIEW_WEIGHT

    return keyword_scores, recent_keywords, recent_view_ids


def score_place(place, keyword_scores, recent_keywords):
    """장소 하나가 선호도 프로필과 얼마나 겹치는지 점수로 환산합니다."""
    score = 0

    for keyword in place_keyword_set(place):
        score += keyword_scores.get(keyword, 0)

    # [기존 방식 유지 - 회귀 방지] 검색 키워드가 이름/주소에 그대로 포함되는 경우도 함께
    # 반영합니다. 이번 고도화 이전에는 이 방식이 전부였으므로, 조회 이력이 아직 없는
    # 사용자에게도 최소한의 추천이 계속 동작하도록 보존합니다.
    for keyword in recent_keywords:
        if keyword and (keyword in place.name or keyword in place.address):
            score += SEARCH_WEIGHT

    return score


def recommend_places_for_user(user):
    """
    사용자의 행동 패턴(검색 키워드 + 선택한 장소) 기반 추천 장소 목록을 반환합니다.
    이미 조회(선택)한 장소는 추천 후보에서 제외합니다.

    반환값: (추천 장소 리스트 - Place 객체, 상위 TOP_N건, 검색/조회 기록이 하나라도 있었는지 여부)
    """
    keyword_scores, recent_keywords, recent_view_ids = build_preference_profile(user)
    has_history = bool(recent_keywords or recent_view_ids)

    if not has_history:
        return [], False

    candidates = Place.objects.exclude(id__in=recent_view_ids)[:CANDIDATE_LIMIT]

    scored = []
    for place in candidates:
        score = score_place(place, keyword_scores, recent_keywords)
        if score > 0:
            scored.append((place, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [place for place, _ in scored[:TOP_N]], True


# --- [장소 상세 - 비슷하거나 가까운 매장] -------------------------------------------
# 장소 상세페이지에서 "이런 곳은 어때요" 추천에 쓰입니다(api/views.py의
# SimilarPlacesView). recommend_places_for_user()/daily_recommended_places()와 달리
# 로그인 여부나 사용자 행동 기록과는 무관하게, 기준 장소 하나를 두고 다른 장소들과의
# 유사도(키워드 겹침)+실제 거리만으로 계산하는 "장소 대 장소" 추천입니다.

EARTH_RADIUS_KM = 6371.0
NEARBY_RADIUS_KM = 2.0          # 이 거리(km) 이내면 "가까운 매장"으로 인정
SIMILARITY_KEYWORD_SCORE = 10   # 겹치는 키워드 1개당 더해지는 점수
PROXIMITY_MAX_SCORE = 10        # 바로 옆(0km)일 때 받는 거리 점수 - 키워드 1개 겹침과 비슷한 비중
SIMILAR_PLACES_LIMIT = 10
SIMILAR_PLACES_CANDIDATE_LIMIT = 500  # 전체 장소가 많아질 때 성능 보호


def _haversine_km(lat1, lng1, lat2, lng2):
    """두 좌표(위도/경도, 도 단위) 사이의 대권 거리(km)를 구합니다."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1, math.sqrt(a)))


def similar_places_for(place, limit=SIMILAR_PLACES_LIMIT):
    """
    [장소 상세 - 비슷하거나 가까운 매장] 기준 장소(place)와 (1) 키워드(위치/업종/분위기,
    PlaceKeyword)가 하나라도 겹치거나, (2) 실제 좌표 기준 NEARBY_RADIUS_KM 이내에 있는
    장소를 후보로 모읍니다 - "비슷하거나 가까운" 이라는 요구사항대로 둘 중 하나만
    만족해도 후보에 포함됩니다(아주 비슷하지만 멀리 있는 곳 / 가깝지만 업종이 전혀 다른
    곳도 모두 나올 수 있음).

    후보 안에서의 순서는 두 신호를 더한 점수로 정렬합니다 - 비슷하면서 동시에 가까운
    곳이 가장 먼저 나옵니다. 광고성 글은 글 단위로 걸러내므로 장소는 제외하지 않습니다.

    좌표가 없는 장소(이 기능 추가 전에 등록돼 latitude/longitude가 비어 있음)는 거리
    계산에서 제외되고 키워드 유사도만으로 평가됩니다 - 재수집하면 좌표가 채워집니다.

    반환값: [{'place': Place, 'distance_km': float|None}, ...] (점수 내림차순, 최대
    limit건)
    """
    base_keywords = place_keyword_set(place)
    base_has_coords = place.latitude is not None and place.longitude is not None
    candidates = Place.objects.exclude(id=place.id)[:SIMILAR_PLACES_CANDIDATE_LIMIT]

    scored = []
    for candidate in candidates:
        shared_keyword_count = len(base_keywords & place_keyword_set(candidate))

        distance_km = None
        if base_has_coords and candidate.latitude is not None and candidate.longitude is not None:
            distance_km = _haversine_km(
                place.latitude, place.longitude, candidate.latitude, candidate.longitude
            )

        is_nearby = distance_km is not None and distance_km <= NEARBY_RADIUS_KM
        if shared_keyword_count == 0 and not is_nearby:
            continue  # 비슷하지도 가깝지도 않음 - 후보에서 제외

        proximity_score = 0
        if is_nearby:
            proximity_score = (NEARBY_RADIUS_KM - distance_km) / NEARBY_RADIUS_KM * PROXIMITY_MAX_SCORE

        score = shared_keyword_count * SIMILARITY_KEYWORD_SCORE + proximity_score
        scored.append((candidate, score, distance_km))

    scored.sort(key=lambda row: row[1], reverse=True)
    return [
        {'place': candidate, 'distance_km': distance_km}
        for candidate, _, distance_km in scored[:limit]
    ]


# --- [오늘의 추천 장소] 로그인 첫 화면: 식당/카페/술집 각 1곳씩 -----------------------

def _tokenize_search_keywords(search_keywords):
    """검색어 문자열 목록을 공백 기준으로 토큰화합니다. (SearchView의 검색어 토큰화와 동일한 방식)"""
    tokens = []
    for kw in search_keywords:
        tokens.extend(t for t in kw.split() if t)
    return tokens


def _matched_keyword_counts(search_tokens, keyword_types):
    """
    검색어 토큰들이 실제로 존재하는 keyword_types(예: ['location'])의 PlaceKeyword 값과
    얼마나 자주 겹치는지 셉니다. 토큰과 키워드 값이 서로 부분 문자열로 겹치면(양방향
    - "유성구"와 "대전 유성구"처럼) 매칭으로 인정합니다.
    """
    candidate_keywords = list(
        PlaceKeyword.objects.filter(keyword_type__in=keyword_types)
        .values_list('keyword', flat=True).distinct()
    )
    counts = Counter()
    for token in search_tokens:
        for kw in candidate_keywords:
            if token in kw or kw in token:
                counts[kw] += 1
    return counts


def _pick_best_place(places, location_counts, other_keyword_counts):
    """
    후보 장소들 중 (1) 사용자가 주로 검색한 동네와 겹치는 점수, (2) 그다음 주로 검색한
    연관 키워드(종류/분위기)와 겹치는 점수 순서로 가장 좋은 1곳을 고릅니다. 튜플
    (location_score, keyword_score)로 정렬해 동네 일치를 항상 최우선으로 삼습니다 -
    키워드 매칭 개수가 아무리 많아도 동네가 안 맞는 후보를 앞지르지 못합니다.
    """
    if not places:
        return None

    def sort_key(place):
        place_kws = place_keyword_set(place)
        location_score = sum(location_counts.get(kw, 0) for kw in place_kws)
        keyword_score = sum(other_keyword_counts.get(kw, 0) for kw in place_kws)
        return (location_score, keyword_score)

    return max(places, key=sort_key)


def daily_recommended_places(user):
    """
    [오늘의 추천 장소] 로그인 첫 화면에 식당/카페/술집 각 1곳씩(최대 3곳) 추천합니다.
    recommend_places_for_user()와 달리 오직 "검색 기록"만 사용하고(조회 이력은 반영하지
    않음), 장소 선정 우선순위는 다음과 같습니다:
    1) 사용자가 주로 검색한 동네(location 키워드)와 일치하는지
    2) 그 다음 사용자가 주로 검색한 연관 키워드(종류/분위기)와 얼마나 겹치는지

    광고성 글은 글 단위로 걸러내므로 장소는 후보에서 제외하지 않습니다.

    반환값: (results, has_search_history)
    - results: {'restaurant': Place|None, 'cafe': Place|None, 'bar': Place|None}
      (검색 기록이 있어도 그 카테고리에 맞는 후보가 없으면 None일 수 있습니다)
    - has_search_history: 검색 기록이 하나라도 있었는지 여부(recommend_places_for_user()의
      has_history와 동일한 용도 - 화면에 "기록 없음" 안내를 보여줄지 판단하는 데 사용).
    """
    empty_results = {place_type: None for place_type in PLACE_TYPE_ORDER}

    recent_searches = list(
        SearchLog.objects.filter(user=user).order_by('-created_at')
        .values_list('keyword', flat=True)[:RECENT_SEARCH_LIMIT]
    )
    if not recent_searches:
        return empty_results, False

    search_tokens = _tokenize_search_keywords(recent_searches)
    location_counts = _matched_keyword_counts(search_tokens, ['location'])
    other_keyword_counts = _matched_keyword_counts(search_tokens, ['category', 'mood'])

    candidates_by_type = {place_type: [] for place_type in PLACE_TYPE_ORDER}
    for place in Place.objects.all()[:CANDIDATE_LIMIT]:
        place_type = classify_place_type(category_tokens(place.category))
        if place_type:
            candidates_by_type[place_type].append(place)

    results = {
        place_type: _pick_best_place(places, location_counts, other_keyword_counts)
        for place_type, places in candidates_by_type.items()
    }
    return results, True
