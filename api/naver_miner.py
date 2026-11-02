"""
Naver 지역/블로그/카페글/이미지 검색 API를 이용한 장소 데이터 수집기.

[NAVER API HUB 이관 - 2026-08]
네이버 개발자센터(openapi.naver.com)의 검색 오픈API가 종료되고 NAVER Cloud Platform의
NAVER API HUB(naverapihub.apigw.ntruss.com)로 이관되었습니다. 이 저장소도 함께 변경했습니다.
- 도메인: openapi.naver.com → naverapihub.apigw.ntruss.com
- 경로: /v1/search/{type}.json → /search/v1/{type}
- 인증 헤더: X-Naver-Client-Id/X-Naver-Client-Secret → X-NCP-APIGW-API-KEY-ID/X-NCP-APIGW-API-KEY
- settings.NAVER_CLIENT_ID/NAVER_CLIENT_SECRET(.env)는 이제 NAVER API HUB에서 새로 발급받은
  Client ID/Secret 값을 넣어야 합니다(기존 Developers Center 키는 이관 후 동작하지 않습니다).
참고: https://guide.ncloud-docs.com/docs/apihub-migration (2027-06-30까지 구 방식 병행 지원)

[키워드 기반 장소 구분]
추천 시스템이 참고하던 Review.hashtags(블로그 본문에서 정규식 "#단어"로 그대로 긁어온 것)는
상호명이나 무관한 단어가 많이 섞여 있어 장소 구분용으로 부적절했습니다. 대신 PlaceKeyword
(api/models.py)를 새로 만들어 세 종류로 정리했습니다 - 자세한 규칙은 api/keyword_taxonomy.py 참고.
- location(위치)/category(종류): _store_structural_keywords()가 주소/Place.category에서
  결정적으로 계산합니다(AI 미사용, 비용 없음). 장소 등록 시(_process_place_item)뿐 아니라
  리뷰 최신화(_refresh_place_reviews) 때마다 매번 다시 계산해 교체합니다.
- mood(분위기/특징): _extract_mood_keywords()가 리뷰 내용을 보고 keyword_taxonomy.MOOD_KEYWORDS
  안에서만 AI가 고르게 하고, 목록 밖의 값은 서버에서 걸러냅니다. 리뷰 최신화 때마다 갱신되며,
  소스가 이전과 동일하면(전부 재사용) 재호출을 생략합니다.
Review.hashtags 필드 자체(리뷰 화면에 보이는 태그)는 그대로 유지되며, 추천 스코어링만
PlaceKeyword를 사용하도록 바뀌었습니다(api/recommendation.py 참고).

[오탐 매칭 완화 1단계 - 장소명과 우연히 같은 무관한 글 걸러내기]
장소명만으로 블로그/카페글을 검색하면, 장소명이 흔한 단어/문법 표현과 우연히 같을 때
전혀 무관한 글이 리뷰 소스로 섞이는 문제가 있었습니다(예: 장소명 "알텐데"가 "~ㄹ텐데"라는
흔한 문장 어미와 겹쳐 "와이프도 알텐데"처럼 그 장소와 아무 상관 없는 글이 매칭됨).
_collect_review_source_candidates()에서 두 단계로 완화합니다:
1. 검색어 자체에 지역명을 함께 넣어(예: "알텐데 대전 중구") 네이버 검색이 두 단어를 모두
   포함한 글을 우선 반환하도록 유도합니다.
2. 그렇게 받은 후보 중에서도 지역명/업종 키워드까지 실제로 title/description에 언급된
   "확실한 매칭"을 장소명만 겹치는 "약한 매칭"보다 항상 먼저 채택합니다(_extract_candidates_from_search
   의 strict_match). 확실한 매칭만으로 MAX_REVIEW_SOURCES를 채우면 약한 매칭은 그대로
   잘려나가고, 부족할 때만 보충으로 사용합니다 - 장소 언급이 원래 적은 경우까지 커버리지를
   0으로 만들지 않으면서 오탐 가능성은 최대한 줄이는 절충입니다.

[오탐 매칭 완화 2단계 - 장소명은 맞지만 정보가 없는 글 걸러내기]
1단계를 통과해도(장소명이 진짜로 언급됨) "그 장소 앞을 지나가다가", "~갔었는데 사진을
못 찍었어요"처럼 이름만 스치듯 나오고 실제 내용은 없는 글, 여러 장소를 나열만 하는
목록형 글이 섞일 수 있습니다. api.gemini_service.analyze_review()가 광고 여부 판단과
같은 호출 안에서(추가 비용 없음) has_place_info(그 장소에 대한 실질적인 정보가 있는지)도
함께 판단하고, _refresh_place_reviews()가 이 값이 False인 후보를 광고 확률 평균/대표
리뷰 선정/분위기 키워드 분석/ReviewSource 저장 어디에도 반영하지 않고 제외합니다.
후보 전부가 정보성 없음으로 판정되면 후보를 아예 못 찾은 경우와 동일하게 placeholder로
처리합니다(_save_fallback_placeholder). 이 판정도 ReviewSource.has_place_info에 저장돼,
내용이 바뀌지 않은 글은 재분석 없이 이전 판정을 그대로 재사용합니다.

[오탐 매칭 완화 3단계 - 비-리뷰 콘텐츠 사전 차단 + 동명이점(동일 상호 다른 지점) 구분]
1~2단계는 모두 "장소에 대한 리뷰인지"를 다루지만, 아래 두 문제는 후보 수집 단계에서
원천적으로 걸러야 합니다(_collect_review_source_candidates/_extract_candidates_from_search
참고, 둘 다 AI 분석으로 보내기 전인 후보 추출 시점에 적용됩니다):
1. 리뷰가 아예 아닌 글: 공고글, 체험단/기자단/서포터즈 모집글, 분양/청약/임대 정보 등은
   장소명이 우연히 언급돼도 "그 장소에 대한 리뷰"가 아닙니다. NON_REVIEW_SIGNAL_PATTERNS에
   있는 문구가 title/description에 있으면 _is_non_review_post()가 True를 반환하고, 해당
   후보는 후보 목록에 아예 들어가지 않습니다(has_place_info AI 판정까지 갈 필요조차 없음).
2. 동명이점(이름은 같지만 실제로는 다른 지점/장소): 같은 상호가 같은 시/구 안에 여러
   지점을 낼 수 있어(프랜차이즈 카페 등) 1단계의 region_hint()(시/구 단위)만으로는 다른
   지점에 대한 글까지 "확실한 매칭"으로 잘못 채택할 수 있었습니다. 이를 보강하기 위해
   region_hint()보다 더 구체적인 neighborhood_hint()(동/읍/면 단위, api/recommendation.py)를
   추가하고, 기존의 이진(binary) strict/weak 판정을 4단계 등급(match_tier, 숫자가 작을수록
   확실함)으로 일반화했습니다: 0=동네 일치, 1=지역(시/구) 일치, 2=업종 일치, 3=장소명만
   일치. 등급이 낮은 후보부터 우선 채택해 MAX_REVIEW_SOURCES를 채우므로, 동네까지 일치하는
   후보가 충분하면 다른 동네의 동명이점 후보는 자연히 뒤로 밀리거나 잘려나갑니다.

[키워드 최신화 - 기존 장소 백필]
이 기능이 추가되기 전부터 DB에 있던 장소는 PlaceKeyword가 하나도 없는 상태입니다.
`python manage.py refresh_naver`(전체 장소 대상) 또는 `refresh_naver --only-new`(신규
장소만)를 실행하면 자동으로 채워집니다:
- 위치/종류 키워드는 항상 다시 계산되므로 실행 즉시 채워집니다.
- 분위기 키워드는 원래 "리뷰 소스가 이전과 동일하면 AI 재호출 생략" 최적화가 있었는데,
  기존 장소는 리뷰 내용이 그대로라 이 최적화 때문에 영영 채워지지 않는 문제가 있었습니다.
  그래서 "분위기 키워드가 하나도 없는 장소는 소스가 재사용되더라도 최초 1회는 반드시
  새로 뽑는다"는 예외를 추가했습니다(_extract_mood_keywords 참고). 이미 분위기 키워드가
  있는 장소는 기존처럼 리뷰 내용이 바뀔 때만 재분석합니다.

[로직 분리 + 리뷰 소스 확장]
1. 장소 정보 수집과 리뷰 수집을 완전히 분리했습니다.
   - mine_from_naver() / mine_naver 커맨드: 지역 검색으로 새 장소(이름/주소/설명/사진)만
     등록합니다. 리뷰나 광고 판별은 이 단계에서 하지 않습니다.
   - refresh_existing_places() / refresh_naver 커맨드: DB에 이미 있는 장소들을 대상으로
     리뷰만 수집/최신화합니다. 새로 장소를 찾지 않으므로 지역 검색 API를 호출하지 않습니다.
     신규 등록 직후 리뷰까지 채우려면 `python manage.py refresh_naver --only-new` 를
     이어서 실행하세요.
2. 리뷰 소스를 블로그 1건에서 "블로그 + 카페글" 다건으로 확장했습니다. 장소 하나당 최소
   MIN_REVIEW_SOURCES(기본 10)건을 목표로 모으고(부족하면 모은 만큼만 사용), 최대
   MAX_REVIEW_SOURCES(기본 15)건까지만 분석해 AI 호출 비용을 통제합니다. 각 글을 개별로
   AI 분석한 뒤 ad_probability는 그 평균으로 PlaceAnalysis에 저장합니다. 화면(Review
   목록)에는 이 중 평균에 가장 가까운 대표 1건만 노출합니다 - 원본 소스 전체는
   ReviewSource 테이블에만 보관합니다(api/models.py 참고).
   네이버 지도(플레이스)의 방문자 리뷰는 공식 검색 오픈API로 조회할 방법이 없어(비공식
   페이지 스크래핑이 필요하고 이용약관 위반 소지가 있음) 이번 확장 대상에서 제외했습니다.
3. 리뷰를 다시 모을 때, 새로 수집한 글이 기존에 저장된 ReviewSource와 (출처, URL, 본문)이
   완전히 같으면 AI 재분석을 생략하고 이전 점수를 재사용합니다 - 불필요한 Gemini 호출을
   줄이기 위함입니다.

[DB 자동 축적 - 장소x키워드 조합 + 신규 건수 기준 수집 - 2026-10]
기존에는 "장소"를 제외하는 중복 판별이 상호명(name)만 보고 있어, 같은 이름의 다른
지점(동명이점, 예: 프랜차이즈 카페)이 지역 검색에 다시 잡혀도 "이미 등록됨"으로 건너뛰는
버그가 있었습니다. _is_duplicate_place()로 분리하면서 상호명+주소가 모두 일치할 때만
중복으로 보도록 고쳤습니다(_process_place_item, mine_from_naver 양쪽 모두 반영).

api/collection_targets.py에 미리 정의해둔 장소 리스트 x 키워드 리스트를 조합해 검색어를
자동으로 만들고(예: "대전 둔산동 베이커리카페"), 조합마다 "신규" 장소가 목표 건수만큼
쌓일 때까지 지역 검색 페이지를 계속 넘기는 _fetch_new_local_places() / 이를 오케스트레이션
하는 auto_collect_from_targets()를 추가했습니다(관리 명령: auto_collect). 이미 등록된
장소나 이번 실행에서 이미 처리한 장소는 "신규" 개수에 포함되지 않고, 네이버 지역 검색
페이지네이션이 더 이상 새 결과를 주지 않거나(_fetch_local_places와 동일한 판정) 안전장치
(페이지/시간 상한)에 걸리면 그 조합은 목표에 못 미치더라도 중단하고 다음 조합으로
넘어갑니다. 수식어(분위기 좋은, 감성 등) 리스트를 추가로 조합하는 기능은 1차 구현에서는
보류했습니다 - api/collection_targets.py 상단 설명 참고.
"""
import html
import logging
import re
import time
from collections import Counter
from itertools import zip_longest
from urllib.parse import quote

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

from .gemini_service import analyze_review, extract_mood_keywords
from .keyword_taxonomy import MAX_MOOD_KEYWORDS_PER_PLACE, MOOD_KEYWORDS
from .models import Place, PlaceAnalysis, PlaceImage, PlaceKeyword, Review, ReviewSource
from .recommendation import category_tokens, neighborhood_hint, region_hint

logger = logging.getLogger('api.naver_miner')

User = get_user_model()

REQUEST_TIMEOUT = 6  # seconds
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5
NAME_SUFFIX_PATTERN = r'(시청점|둔산점|본점|대전둔산점|탄방점|갈마점|유성점|중앙로점)$'

# [지역 검색 display 상한] 네이버 지역 검색(local) API는 블로그/카페글 검색과 달리 display를
# 5까지만 받습니다(5 초과 시 400 오류). 대신 start로 페이지를 넘겨서 더 많이 모읍니다.
NAVER_LOCAL_DISPLAY = 5
NAVER_LOCAL_START_MAX = 1000  # 네이버 API의 start 파라미터 상한(1~1000)

DEFAULT_MAX_PLACES_PER_KEYWORD = 20

# [DB 자동 축적 - 안전장치] auto_collect_from_targets()가 조합(장소x키워드) 하나당 "신규"
# 장소가 목표 개수에 도달할 때까지 페이지를 계속 넘기며 기다리되, 검색 시간이 너무
# 길어지는 것(예: 이미 그 동네/키워드 조합을 거의 다 수집해 신규 매장이 거의 안 남은
# 경우)을 막기 위해 아래 두 상한 중 하나라도 먼저 도달하면 "더 이상 불러올 장소가 없다"고
# 보고 그 조합은 중단합니다(네이버 API 자체의 start 상한 1~1000과는 별개의 안전장치).
AUTO_COLLECT_DEFAULT_PER_COMBO = 10
AUTO_COLLECT_MAX_PAGES_PER_COMBO = 40   # 5건 x 40페이지 = 조합 1개당 최대 200건 원본 조회
AUTO_COLLECT_MAX_SECONDS_PER_COMBO = 60  # 조합 1개당 최대 소요 시간(초)

# [리뷰 소스 확장] 블로그/카페글 검색은 display를 100까지 받을 수 있어(지역 검색과 다름),
# 한 번의 요청으로 후보를 최대한 넉넉히 모은 뒤 장소명이 포함된 것만 걸러냅니다.
REVIEW_SEARCH_DISPLAY = 100
MIN_REVIEW_SOURCES = 10  # 장소 하나당 목표로 모으는 최소 리뷰 소스 수 (부족하면 모은 만큼만 사용)
MAX_REVIEW_SOURCES = 15  # AI 분석 비용/시간을 통제하기 위한 상한

# [비-리뷰 콘텐츠 사전 차단] 리뷰 성격이 아예 아닌 글(공고/모집/분양 정보 등)은 AI 분석으로
# 보낼 필요도 없이 여기서 원천 차단합니다 - 흔한 문구를 미리 걸러 후보 자체에서 제외해
# 비용을 아끼고 데이터 품질도 높입니다(_is_non_review_post 참고). 오탐(진짜 후기를 잘못
# 걸러냄)을 피하기 위해 일부러 여러 단어로 이뤄진 구체적인 문구만 사용합니다 - "이벤트"
# 처럼 후기에도 흔히 나오는 단일 단어는 넣지 않습니다.
NON_REVIEW_SIGNAL_PATTERNS = [
    '체험단 모집', '서포터즈 모집', '기자단 모집', '리뷰어 모집', '참가자 모집',
    '이벤트 참여', '경품 이벤트',
    '분양', '입주자모집공고', '모델하우스', '청약',
    '임대문의', '임대 문의', '구인공고', '채용공고', '구인구직', '아르바이트 모집', '알바 모집',
]

# [NAVER API HUB] 도메인/경로가 또 바뀌더라도 settings.py(.env)만 고치면 되도록 설정값으로 분리.
NAVER_API_BASE_URL = getattr(
    settings, 'NAVER_API_BASE_URL', 'https://naverapihub.apigw.ntruss.com/search/v1'
).rstrip('/')


def _search_url(search_type, query, display, start=None, extra_params=None):
    # 검색어에 공백/특수문자가 그대로 들어가는 문제를 막기 위해 quote()로 URL 인코딩합니다.
    url = f"{NAVER_API_BASE_URL}/{search_type}?query={quote(query)}&display={display}"
    if start is not None:
        url += f"&start={start}"
    # [이미지 정확도 개선] filter(이미지 크기)처럼 검색 타입별로만 쓰는 추가 파라미터를
    # 위해 범용으로 열어둡니다. local/blog/cafearticle 검색은 extra_params 없이 그대로
    # 호출하므로 기존 동작에는 영향이 없습니다.
    if extra_params:
        for key, value in extra_params.items():
            url += f"&{key}={quote(str(value))}"
    return url


def _get_naver_headers():
    naver_client_id = getattr(settings, 'NAVER_CLIENT_ID', '')
    naver_client_secret = getattr(settings, 'NAVER_CLIENT_SECRET', '')
    if not naver_client_id or not naver_client_secret:
        return None
    return {
        "X-NCP-APIGW-API-KEY-ID": naver_client_id,
        "X-NCP-APIGW-API-KEY": naver_client_secret,
    }


def _get_default_user():
    try:
        return User.objects.get(id=1)
    except User.DoesNotExist:
        return User.objects.first()


def _request_with_retry(url, headers):
    """
    [오류 감소] 기존에는 requests.get()에 timeout이 없어 Naver 서버 응답이 느리면 크롤링
    전체가 무한정 멈출 수 있었고, 일시적인 429(요청 과다)/5xx 오류에도 재시도 없이 바로
    실패로 처리되었습니다. timeout + 지수 백오프 재시도를 공통 헬퍼로 분리했습니다.
    성공하면 requests.Response를, 끝내 실패하면 None을 반환합니다(예외를 던지지 않음).
    """
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning("요청 실패(%s/%s): %s - %s", attempt + 1, MAX_RETRIES + 1, url, exc)
        else:
            if response.status_code == 200:
                return response
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {response.status_code}"
                logger.warning(
                    "재시도 대상 응답(%s/%s): %s - status=%s",
                    attempt + 1, MAX_RETRIES + 1, url, response.status_code
                )
            else:
                logger.error("요청 실패(재시도 안 함): %s - status=%s", url, response.status_code)
                return None

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    logger.error("최종 요청 실패: %s - %s", url, last_error)
    return None


def _fetch_image_links(keyword, headers, max_count, filter_size=None):
    """
    [이미지 정확도 개선 - 공용 헬퍼] filter_size를 넘기면 네이버 이미지 검색 API의
    filter 파라미터(large=가로/세로 각각 300px 이상, medium=640x480 이상)로 결과를
    제한합니다. None이면 필터 없이(filter=all과 동일) 요청합니다.
    """
    extra_params = {'filter': filter_size} if filter_size else None
    url = _search_url('image', keyword, max_count, extra_params=extra_params)
    response = _request_with_retry(url, headers)
    if not response:
        return []
    try:
        items = response.json().get('items', [])
    except ValueError:
        logger.error("이미지 검색 응답 JSON 파싱 실패: keyword=%s filter=%s", keyword, filter_size)
        return []
    return [item.get('link') for item in items if item.get('link')]


def get_exact_images_from_naver(keyword, headers, max_count=5):
    """
    [이미지 정확도 개선] 먼저 filter='large'(가로/세로 각각 300px 이상)로 요청해, 글
    본문에 흔히 섞여 있는 작은 썸네일/아이콘/로고/프로필 사진처럼 매장과 무관할
    가능성이 큰 이미지를 1차로 걸러냅니다. 다만 이건 여전히 "상호명+지역" 텍스트와
    유사한 이미지를 웹 전체에서 찾는 일반 이미지 검색이라(실제 매장 사진이라는 보장은
    없음), 완전히 관련 없는 사진을 100% 없애주진 않습니다 - sort는 기본값인 sim(유사도
    순)을 그대로 사용합니다.

    소규모 매장은 큰 이미지가 거의 없어 filter='large'로 0건이 나올 수 있으므로, 그
    경우에만 필터 없이 한 번 더 시도해 사진이 아예 비는 상황을 피합니다.
    """
    large_links = _fetch_image_links(keyword, headers, max_count, filter_size='large')
    if large_links:
        return large_links
    return _fetch_image_links(keyword, headers, max_count)


def _refined_short_name(place_name):
    return re.sub(NAME_SUFFIX_PATTERN, '', place_name).strip()


def _page_signature(page_items):
    """페이지 중복 판별용 서명. title 목록을 그대로 비교합니다."""
    return tuple(item.get("title", "") for item in page_items)


def _extract_name_address(item):
    """
    [중복 판별 공용 헬퍼] 지역 검색 결과 1건에서 (상호명, 주소)만 뽑아냅니다.
    _process_place_item/_is_duplicate_place/_fetch_new_local_places가 공용으로 사용합니다.
    """
    raw_title = item.get("title", "")
    name = html.unescape(re.sub(r'<[^>]+>', '', raw_title))
    address = item.get("roadAddress") or item.get("address") or "주소 미확인"
    return name, address


def _extract_coordinates(item):
    """
    [거리 기반 추천] 네이버 지역 검색 API 응답의 mapx(경도)/mapy(위도)는 WGS84 좌표에
    10^7을 곱한 문자열입니다(공식 문서 기준 - KATEC 등 별도 좌표계 변환 불필요).
    10,000,000으로 나누면 바로 도(degree) 단위 위도/경도가 됩니다. 값이 없거나 숫자로
    변환할 수 없으면 (None, None)을 반환하고, 그 장소는 거리 기반 추천(
    api/recommendation.py의 similar_places_for)에서 제외되고 키워드 유사도만으로
    평가됩니다.
    """
    try:
        longitude = float(item.get('mapx')) / 10_000_000
        latitude = float(item.get('mapy')) / 10_000_000
    except (TypeError, ValueError):
        return None, None
    return latitude, longitude


def _is_duplicate_place(name, address):
    """
    [중복 판별 - 상호명+주소 기준] 상호명만으로 중복을 판단하면 같은 이름의 다른 지점
    (동명이점, 예: 프랜차이즈 카페)까지 "이미 등록됨"으로 잘못 건너뛰게 됩니다. 반대로
    주소만으로 판단하면 한 건물/상가에 입점한 서로 다른 매장을 같은 곳으로 오인할 수
    있습니다. 두 값이 모두 일치할 때만 같은 매장으로 간주합니다.
    """
    return Place.objects.filter(name=name, address=address).exists()


def _fetch_local_places(search_keyword, headers, max_results, request_interval):
    """
    [키워드당 수집 개수 확대] 지역 검색 API는 한 번 요청에 최대 5건(display)만 줍니다.
    문서상으로는 start를 5씩 늘리면 다음 페이지가 온다고 되어 있지만, 실제로는 지역 검색
    (local) 엔드포인트가 start 파라미터를 무시하고 항상 동일한 첫 페이지를 반환하는 경우가
    있습니다(2026-08 NAVER API HUB 기준 실측 확인). 이 경우 그대로 두면 동일한 결과를
    max_results/5 번 반복 요청하며 API 호출만 낭비하게 됩니다.

    따라서 새로 받은 페이지가 바로 직전 페이지와 완전히 동일하면(=start가 실제로 페이지를
    넘기지 못한 것으로 판단) 그 자리에서 즉시 중단합니다. 이 함수가 반환하는 개수가
    max_results보다 적더라도 정상이며, 그만큼은 이 키워드로는 더 이상 새로운 장소를 얻을 수
    없다는 뜻입니다. 더 많은 장소가 필요하면 mine_naver 커맨드에 다른 키워드를 추가로
    넘겨서 수집하세요 (예: "대전 유성구 맛집" "대전 유성구 카페" "대전 유성구 국밥").
    """
    collected = []
    start = 1
    previous_signature = None
    while len(collected) < max_results and start <= NAVER_LOCAL_START_MAX:
        display = min(NAVER_LOCAL_DISPLAY, max_results - len(collected))
        url = _search_url('local', search_keyword, display, start=start)
        response = _request_with_retry(url, headers)

        if not response:
            logger.warning("지역 검색 페이지 요청 실패, 여기까지만 수집합니다: keyword=%s start=%s", search_keyword, start)
            break

        try:
            page_items = response.json().get("items", [])
        except ValueError:
            logger.error("지역 검색 응답 JSON 파싱 실패: keyword=%s start=%s", search_keyword, start)
            break

        if not page_items:
            break

        current_signature = _page_signature(page_items)
        if start > 1 and current_signature == previous_signature:
            # start가 실제로는 페이지를 넘기지 않고 동일한 결과를 되돌려준 경우.
            # 더 요청해봐야 같은 결과만 반복되므로 API 호출 낭비를 막기 위해 중단합니다.
            logger.info(
                "[%s] start=%s 페이지가 이전 페이지와 동일합니다. 이 키워드로는 지역 검색 "
                "페이지네이션이 더 이상 새 결과를 주지 않는 것으로 보여 수집을 중단합니다 "
                "(현재까지 %s건 확보). 더 많은 장소가 필요하면 다른 키워드를 추가로 사용하세요.",
                search_keyword, start, len(collected)
            )
            break

        collected.extend(page_items)
        previous_signature = current_signature

        if len(page_items) < display:
            # 이번 페이지가 요청한 개수보다 적게 왔다는 건 더 가져올 결과가 없다는 뜻.
            break

        start += NAVER_LOCAL_DISPLAY
        time.sleep(request_interval)

    return collected


def _fetch_new_local_places(search_keyword, headers, target_new_count, request_interval,
                             seen_in_run, max_pages=AUTO_COLLECT_MAX_PAGES_PER_COMBO,
                             max_seconds=AUTO_COLLECT_MAX_SECONDS_PER_COMBO):
    """
    [DB 자동 축적] search_keyword로 지역 검색 결과를 페이지 단위(5건씩)로 가져오면서,
    이미 DB에 등록됐거나(_is_duplicate_place) 이번 실행에서 이미 처리한(seen_in_run) 장소는
    "신규" 개수에 포함하지 않고(=API 호출은 소모하지만 목표 건수에는 안 셈) 건너뛰어,
    신규로 판단되는 장소가 target_new_count건 모일 때까지 계속 다음 페이지를 요청합니다.

    seen_in_run은 (name, address) 튜플 집합입니다. 호출부(auto_collect_from_targets)가
    여러 조합에 걸쳐 같은 집합을 공유해서 넘기면, 한 장소가 여러 조합의 검색 결과에
    겹쳐 나오더라도 신규 개수로 두 번 세지 않습니다.

    중단 조건 (위에서부터 먼저 만족하는 것):
    - target_new_count건 확보 → 'target_reached'
    - 지역 검색 페이지네이션이 더 이상 새 결과를 주지 않음(빈 페이지 / 직전 페이지와 완전히
      동일한 페이지 - _fetch_local_places와 동일한 판정 / 요청한 개수보다 적게 옴) →
      'exhausted' - 이 키워드로는 더 가져올 장소가 없다는 뜻
    - max_pages 도달(안전장치, 네이버 API 자체 상한과는 별개) → 'max_pages'
    - max_seconds 경과(안전장치) → 'timeout'
    - 네이버 API의 start 파라미터 상한(1~1000) 도달 → 'api_limit'

    반환값: (new_items, raw_fetched_count, stopped_reason). new_items는 신규로 판단된
    원본 item dict 목록입니다 - 이 함수 자체는 DB에 아무 것도 쓰지 않으며, 실제 Place
    생성은 호출부가 _process_place_item으로 처리합니다.
    """
    new_items = []
    raw_fetched_count = 0
    start = 1
    previous_signature = None
    started_at = time.monotonic()

    while True:
        if len(new_items) >= target_new_count:
            return new_items, raw_fetched_count, 'target_reached'
        if start > NAVER_LOCAL_START_MAX:
            return new_items, raw_fetched_count, 'api_limit'
        if raw_fetched_count // NAVER_LOCAL_DISPLAY >= max_pages:
            return new_items, raw_fetched_count, 'max_pages'
        if time.monotonic() - started_at >= max_seconds:
            return new_items, raw_fetched_count, 'timeout'

        url = _search_url('local', search_keyword, NAVER_LOCAL_DISPLAY, start=start)
        response = _request_with_retry(url, headers)
        if not response:
            logger.warning(
                "지역 검색 페이지 요청 실패, 여기까지만 수집합니다: keyword=%s start=%s",
                search_keyword, start
            )
            return new_items, raw_fetched_count, 'exhausted'

        try:
            page_items = response.json().get("items", [])
        except ValueError:
            logger.error("지역 검색 응답 JSON 파싱 실패: keyword=%s start=%s", search_keyword, start)
            return new_items, raw_fetched_count, 'exhausted'

        if not page_items:
            return new_items, raw_fetched_count, 'exhausted'

        current_signature = _page_signature(page_items)
        if start > 1 and current_signature == previous_signature:
            logger.info(
                "[%s] start=%s 페이지가 이전 페이지와 동일합니다. 더 이상 새 결과가 없는 것으로 "
                "보여 수집을 중단합니다 (신규 %s/%s건 확보).",
                search_keyword, start, len(new_items), target_new_count
            )
            return new_items, raw_fetched_count, 'exhausted'

        raw_fetched_count += len(page_items)
        previous_signature = current_signature

        for raw_item in page_items:
            name, address = _extract_name_address(raw_item)
            if not name:
                continue
            key = (name, address)
            if key in seen_in_run:
                # 이미 등록됐거나(_is_duplicate_place) 이번 실행의 다른 조합에서 이미
                # 신규로 집은 장소. API 호출은 이미 소모됐지만 목표 건수에는 포함하지 않음.
                continue
            seen_in_run.add(key)
            if _is_duplicate_place(name, address):
                continue
            new_items.append(raw_item)
            if len(new_items) >= target_new_count:
                break

        if len(new_items) >= target_new_count:
            return new_items, raw_fetched_count, 'target_reached'

        if len(page_items) < NAVER_LOCAL_DISPLAY:
            # 요청한 개수보다 적게 왔다는 건 더 가져올 결과가 없다는 뜻.
            return new_items, raw_fetched_count, 'exhausted'

        start += NAVER_LOCAL_DISPLAY
        time.sleep(request_interval)


def _process_place_item(item, headers, request_interval):
    """
    [장소 정보 수집 전용 - 리뷰 로직과 분리] 지역 검색 결과 1건으로 Place(+사진)만
    생성합니다. 리뷰/광고 판별은 여기서 하지 않습니다 - refresh_existing_places() /
    refresh_naver 커맨드가 별도로 담당합니다.

    이미 등록된 장소(상호명+주소 일치, _is_duplicate_place 참고)는 아무 것도 하지 않고
    건너뜁니다(장소 정보 재수집도 생략). 신규 장소가 아니면 None을, 새로 만들어진 Place면
    그 객체를 반환합니다.
    """
    exact_place_name, exact_address = _extract_name_address(item)
    if not exact_place_name:
        logger.warning("장소명이 비어 있는 항목을 건너뜁니다: %s", item)
        return None

    if _is_duplicate_place(exact_place_name, exact_address):
        logger.info(
            "이미 등록된 장소(상호명+주소 일치) - 건너뜁니다: %s (%s)",
            exact_place_name, exact_address
        )
        return None

    # [추가 - 추천 시스템] 네이버 지역 검색 API의 category(예: "음식점>한식>한정식")는 업종
    # 정보 그대로 category 필드에 저장하고, description은 기존처럼 category/description 중
    # 있는 것을 사용합니다 (api/recommendation.py가 category 필드를 업종 매칭에 사용합니다).
    raw_category = html.unescape(re.sub(r'<[^>]+>', '', item.get("category") or ""))
    raw_item_description = html.unescape(re.sub(r'<[^>]+>', '', item.get("description") or ""))
    description = raw_category or raw_item_description or f"{exact_place_name} 정보입니다."
    refined_name_short = _refined_short_name(exact_place_name)

    # [이미지 정확도 개선] 주소 첫 토큰(시 단위, 예: "대전")만 쓰면 같은 시의 다른
    # 구/동에 있는 동명 매장이나 전혀 무관한 글까지 섞일 여지가 큽니다. region_hint()로
    # 시/구 단위(예: "대전 유성구")까지 붙여 검색 범위를 더 좁힙니다 - 이미 location
    # 키워드/리뷰 소스 매칭에서 쓰는 것과 같은 함수라 기준이 서로 어긋나지 않습니다.
    image_region_hint = region_hint(exact_address) if exact_address and exact_address != "주소 미확인" else ""
    image_query = f"{image_region_hint} {refined_name_short}".strip()
    # [오류 감소] 이미지 수집이 실패해도(예외 발생) Place를 만들다 만 상태로 남기지 않도록,
    # Place.objects.create()보다 먼저 호출합니다 - 여기서 예외가 나면 이 장소는 통째로
    # 건너뛰고 DB에 아무 것도 남지 않습니다(다음 실행 때 다시 신규 장소로 재시도됩니다).
    real_images = get_exact_images_from_naver(image_query, headers, max_count=5)
    time.sleep(request_interval)

    latitude, longitude = _extract_coordinates(item)

    place = Place.objects.create(
        name=exact_place_name,
        address=exact_address,
        description=description[:1000],
        category=raw_category[:150],
        latitude=latitude,
        longitude=longitude,
    )
    logger.info("신규 장소 등록: %s", exact_place_name)

    for img_url in real_images:
        PlaceImage.objects.get_or_create(place=place, image_url=img_url)

    _store_structural_keywords(place)

    return place


def _store_structural_keywords(place):
    """
    [키워드 기반 장소 구분] 위치/종류 키워드는 주소·업종에서 결정적으로 계산합니다(AI 미사용,
    비용 없음). 분위기(mood) 키워드는 리뷰 내용이 필요해 여기서 만들지 않고
    _refresh_place_reviews()에서 별도로 채웁니다.

    [키워드 최신화 - 멱등성] 장소 등록 시(_process_place_item)뿐 아니라 리뷰 최신화
    (_refresh_place_reviews) 때도 매번 호출됩니다. 비용 없는 결정적 계산이라 여러 번
    다시 만들어도 문제없고, 덕분에 이 기능이 추가되기 전부터 있던 기존 장소도 다음
    `refresh_naver` 실행 한 번으로 위치 키워드가 자연스럽게 채워집니다(백필). 그래서 매번
    기존 location/category 키워드를 지우고 새로 계산한 값으로 교체합니다(중복 생성 방지).
    """
    keywords = []

    region = region_hint(place.address)
    if region:
        keywords.append(('location', region))

    # 동/읍/면 단위까지 더 세밀하게 (neighborhood_hint 참고 - 리뷰 소스 매칭에서도 동일한
    # 함수로 "이름은 같지만 다른 지점"을 걸러내는 데 재사용합니다).
    neighborhood = neighborhood_hint(place.address)
    if neighborhood:
        keywords.append(('location', neighborhood))

    for token in category_tokens(place.category):
        keywords.append(('category', token))

    unique_keywords = list(dict.fromkeys(keywords))  # (type, keyword) 튜플 기준 중복 제거, 순서 유지

    place.keywords.filter(keyword_type__in=['location', 'category']).delete()
    if unique_keywords:
        PlaceKeyword.objects.bulk_create([
            PlaceKeyword(place=place, keyword_type=keyword_type, keyword=keyword)
            for keyword_type, keyword in unique_keywords
        ])


def mine_from_naver(search_keywords, request_interval=0.2, max_places_per_keyword=DEFAULT_MAX_PLACES_PER_KEYWORD):
    """
    [자동화 + 로직 분리] search_keywords에 문자열 하나뿐 아니라 리스트/튜플을 넘기면 여러
    키워드를 한 번의 호출로 순차 처리합니다. 이 함수는 장소 정보(Place/사진)만 수집하고
    리뷰/광고 판별은 하지 않습니다 - 새로 등록된 장소의 리뷰까지 채우려면 이어서
    `python manage.py refresh_naver --only-new` 를 실행하세요.

    request_interval은 Naver API 과다 호출(429)을 피하기 위해 요청 사이에 두는 최소 대기(초)입니다.
    max_places_per_keyword는 키워드 1개당 수집할 최대 장소 수입니다(지역 검색 API 자체는 한 번에
    5건까지만 주기 때문에, 내부적으로 여러 페이지를 이어붙여 이 개수를 채웁니다).

    [장소x키워드 조합으로 "신규" 건수를 목표로 자동 수집하려면] 이 함수 대신
    auto_collect_from_targets()(관리 명령: auto_collect)를 사용하세요 - 이 함수는 키워드당
    "조회" 개수를 채우는 것이 목표인 반면, auto_collect_from_targets()는 이미 등록된 장소를
    세지 않고 "신규" 개수를 목표로 채웁니다.
    """
    if isinstance(search_keywords, str):
        search_keywords = [search_keywords]

    headers = _get_naver_headers()
    if not headers:
        logger.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET가 .env에 설정되어 있지 않습니다.")
        return []

    seen_in_this_run = set()
    new_places = []

    for search_keyword in search_keywords:
        logger.info("=== [%s] 수집을 시작합니다 (최대 %s건) ===", search_keyword, max_places_per_keyword)
        places_items = _fetch_local_places(search_keyword, headers, max_places_per_keyword, request_interval)

        if not places_items:
            logger.error("지역 검색 결과가 없거나 요청에 실패해 이 키워드는 건너뜁니다: %s", search_keyword)
            continue

        logger.info("[%s] 지역 검색으로 %s건 확보", search_keyword, len(places_items))

        for item in places_items:
            place_name, place_address = _extract_name_address(item)
            if not place_name:
                continue
            key = (place_name, place_address)
            if key in seen_in_this_run:
                # 여러 키워드 검색 결과가 겹치는 경우 같은 장소(상호명+주소 일치)를 이번
                # 실행에서 두 번 처리하지 않음. (상호명만으로 비교하면 동명이점을 잘못
                # 걸러낼 수 있어 주소까지 함께 봅니다 - _is_duplicate_place와 동일한 기준.)
                continue
            seen_in_this_run.add(key)

            try:
                place = _process_place_item(item, headers, request_interval)
                if place is not None:
                    new_places.append(place)
            except Exception:
                # [오류 감소] 장소 1건 처리 중 예상치 못한 예외가 나도 전체 배치가 멈추지
                # 않고 다음 장소로 계속 진행하도록 합니다. 원인 추적을 위해 스택트레이스를 남깁니다.
                logger.exception("장소 처리 중 오류 발생, 건너뜁니다: %s", place_name)
                continue

        logger.info("=== [%s] 지역 검색 처리 완료 (누적 확인 장소 %s건) ===", search_keyword, len(seen_in_this_run))

    logger.info(
        "전체 키워드 수집 파이프라인 종료. 신규 장소 %s건 등록. 리뷰까지 채우려면 "
        "`python manage.py refresh_naver --only-new` 를 실행하세요.",
        len(new_places)
    )
    return new_places


def auto_collect_from_targets(search_queries, per_combo=AUTO_COLLECT_DEFAULT_PER_COMBO,
                               request_interval=0.2, max_pages=AUTO_COLLECT_MAX_PAGES_PER_COMBO,
                               max_seconds=AUTO_COLLECT_MAX_SECONDS_PER_COMBO):
    """
    [DB 자동 축적] api/collection_targets.py의 장소x키워드 조합(search_queries, 예:
    "대전 둔산동 베이커리카페")을 순서대로 처리합니다. 조합마다 "신규" 장소가 per_combo건
    모일 때까지 지역 검색 페이지를 계속 넘기고(_fetch_new_local_places), 신규로 확인된
    원본 항목만 _process_place_item으로 실제 Place를 생성합니다.

    이미 등록된 장소이거나 이번 실행의 다른 조합에서 이미 처리한 장소는 "신규" 개수에
    포함되지 않습니다 - API는 더 호출되지만(페이지를 더 넘겨야 하므로) 그만큼 DB에
    쌓이는 건수가 줄어들지는 않습니다. 한 조합에서 더 이상 새로운 장소를 찾을 수 없으면
    (페이지네이션 고갈) 또는 안전장치(페이지/시간 상한)에 걸리면 목표에 못 미치더라도
    그 조합은 중단하고 다음 조합으로 넘어갑니다.

    mine_from_naver와 마찬가지로 장소 정보(이름/주소/사진)만 수집합니다 - 리뷰까지
    채우려면 이어서 `python manage.py refresh_naver --only-new`를 실행하세요.

    반환값: (new_places, summary) - new_places는 새로 생성된 Place 객체 목록, summary는
    조합별 결과({'query','created','target','raw_fetched','stopped_reason'}) 목록입니다.
    """
    headers = _get_naver_headers()
    if not headers:
        logger.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET가 .env에 설정되어 있지 않습니다.")
        return [], []

    seen_in_run = set()
    new_places = []
    summary = []

    stopped_reason_labels = {
        'target_reached': '목표 달성',
        'exhausted': '더 이상 불러올 장소 없음',
        'max_pages': '페이지 상한 도달(안전장치)',
        'timeout': '시간 초과(안전장치)',
        'api_limit': 'API 조회 상한(start=1000) 도달',
    }

    for search_keyword in search_queries:
        logger.info("=== [%s] 자동 수집 시작 (목표: 신규 %s건) ===", search_keyword, per_combo)
        new_items, raw_fetched, stopped_reason = _fetch_new_local_places(
            search_keyword, headers, per_combo, request_interval,
            seen_in_run, max_pages=max_pages, max_seconds=max_seconds,
        )

        created_count = 0
        for item in new_items:
            try:
                place = _process_place_item(item, headers, request_interval)
                if place is not None:
                    new_places.append(place)
                    created_count += 1
            except Exception:
                logger.exception("장소 처리 중 오류 발생, 건너뜁니다: %s", item.get("title", ""))
                continue

        reason_label = stopped_reason_labels.get(stopped_reason, stopped_reason)
        logger.info(
            "=== [%s] 완료: 신규 %s/%s건 등록 (원본 %s건 조회, 중단 사유: %s) ===",
            search_keyword, created_count, per_combo, raw_fetched, reason_label
        )
        summary.append({
            'query': search_keyword,
            'created': created_count,
            'target': per_combo,
            'raw_fetched': raw_fetched,
            'stopped_reason': reason_label,
        })

    logger.info(
        "전체 자동 수집 파이프라인 종료. 신규 장소 %s건 등록. 리뷰까지 채우려면 "
        "`python manage.py refresh_naver --only-new` 를 실행하세요.",
        len(new_places)
    )
    return new_places, summary


def _is_non_review_post(title, desc):
    """제목/본문에 공고·모집·분양 등 리뷰 성격이 아닌 글의 흔한 신호 문구가 있으면 True."""
    combined = f"{title} {desc}"
    return any(pattern in combined for pattern in NON_REVIEW_SIGNAL_PATTERNS)


def _compute_match_tier(title, desc, signal_tiers):
    """
    후보 글이 장소와 얼마나 구체적으로 일치하는지 등급(0이 가장 확실함)을 계산합니다.
    signal_tiers는 [(등급, 신호문자열), ...] 형태이며 _collect_review_source_candidates가
    만듭니다. 일치하는 신호가 여러 개면 그중 가장 확실한(숫자가 작은) 등급을 씁니다.
    아무 신호도 없으면(장소명만 일치) 3을 반환합니다.
    """
    combined = f"{title} {desc}"
    matched_tiers = [tier for tier, token in signal_tiers if token and token in combined]
    return min(matched_tiers) if matched_tiers else 3


def _extract_candidates_from_search(search_type, search_query, headers, refined_name_short, signal_tiers):
    """
    블로그/카페글 검색 결과 중 장소명이 제목/본문에 포함된 것만 리뷰 소스 후보로 추출합니다.

    [비-리뷰 콘텐츠 사전 차단] 공고/모집/분양 등 리뷰가 아예 아닌 글(_is_non_review_post)은
    AI로 보내기 전에 여기서 완전히 제외합니다 - 후보 목록에 아예 들어가지 않습니다.

    [오탐 매칭 완화] 장소명이 짧거나 흔한 단어/문법 표현과 우연히 같으면("알텐데"라는
    장소명이 "~ㄹ텐데"라는 흔한 어미와 겹쳐 "와이프도 알텐데" 같은 전혀 무관한 글이
    매칭되는 식) 장소명 포함 여부만으로는 걸러낼 수 없습니다. 그래서 후보마다 얼마나
    구체적인 위치/업종 신호까지 함께 언급됐는지 등급(match_tier)을 매겨두고, 실제로 몇
    건을 채택할지는 이 함수를 호출하는 _collect_review_source_candidates()가 결정합니다
    - 등급이 낮을수록(더 확실할수록) 먼저 채택됩니다.
    """
    url = _search_url(search_type, search_query, REVIEW_SEARCH_DISPLAY)
    response = _request_with_retry(url, headers)
    if not response:
        return []

    try:
        items = response.json().get("items", [])
    except ValueError:
        logger.error("%s 검색 응답 JSON 파싱 실패: query=%s", search_type, search_query)
        return []

    candidates = []
    for it in items:
        title = html.unescape(re.sub(r'<[^>]+>', '', it.get("title", "")))
        desc = html.unescape(re.sub(r'<[^>]+>', '', it.get("description", "")))

        if _is_non_review_post(title, desc):
            continue

        if refined_name_short and refined_name_short not in title and refined_name_short not in desc:
            continue

        content = f"[{title}] {desc}".strip()
        if not content:
            continue

        candidates.append({
            "source_type": search_type,
            "title": title,
            "url": it.get("link") or "",
            "content": content,
            "match_tier": _compute_match_tier(title, desc, signal_tiers),
        })

    return candidates


def _collect_review_source_candidates(place, headers, request_interval):
    """
    [리뷰 소스 확장 + 오탐 매칭 완화 3단계] 블로그 + 카페글 검색에서 장소명이 포함된
    후보를 모두 모은 뒤, MAX_REVIEW_SOURCES건까지만 사용합니다.

    검색어 자체에도 지역명을 함께 넣어(예: "알텐데 대전 중구") 네이버 검색이 두 단어를
    모두 포함한 글을 우선 반환하도록 유도합니다. 그렇게 받은 후보는 얼마나 구체적인
    신호까지 title/description에 실제로 언급됐는지에 따라 4개 등급(match_tier, 숫자가
    작을수록 확실함)으로 나누고, 등급이 낮은 후보부터 채택합니다:
    0) 동/읍/면 단위(neighborhood_hint) 언급 - 같은 상호의 다른 지점(동명이점)까지
       구분할 수 있는 가장 강한 신호
    1) 시/구 단위(region_hint) 언급
    2) 업종 키워드(category_tokens) 언급
    3) 장소명만 일치(위 신호가 전혀 없음) - 오탐 가능성이 가장 큼

    등급 0~2만으로 MAX_REVIEW_SOURCES를 채우면 등급 3(약한 매칭)은 그대로 잘려나갑니다
    - 부족할 때만 보충으로 사용해, "와이프도 알텐데"처럼 장소명과 우연히 같은 무관한
    글이나 실제로는 다른 지점(동명이점)에 대한 글이 섞이는 경우를 최대한 줄입니다.

    MIN_REVIEW_SOURCES건에 못 미치면 경고만 남기고 모은 만큼 그대로 사용합니다(장소가
    실제로 온라인에 언급이 적을 수 있으므로 실패로 취급하지 않습니다).
    """
    refined_name_short = _refined_short_name(place.name)
    neighborhood = neighborhood_hint(place.address)
    region = region_hint(place.address)
    search_query = f"{refined_name_short} {region}".strip() if region else refined_name_short
    signal_tiers = [
        (0, neighborhood),
        (1, region),
        *[(2, tok) for tok in category_tokens(place.category)],
    ]
    signal_tiers = [(tier, tok) for tier, tok in signal_tiers if tok]

    blog_candidates = _extract_candidates_from_search(
        'blog', search_query, headers, refined_name_short, signal_tiers
    )
    time.sleep(request_interval)
    cafe_candidates = _extract_candidates_from_search(
        'cafearticle', search_query, headers, refined_name_short, signal_tiers
    )

    def _interleave(items_a, items_b):
        merged = []
        for a, b in zip_longest(items_a, items_b):
            if a:
                merged.append(a)
            if b:
                merged.append(b)
        return merged

    ordered = []
    for tier in (0, 1, 2, 3):
        ordered.extend(_interleave(
            [c for c in blog_candidates if c["match_tier"] == tier],
            [c for c in cafe_candidates if c["match_tier"] == tier],
        ))
    total_found = len(blog_candidates) + len(cafe_candidates)

    if total_found < MIN_REVIEW_SOURCES:
        logger.warning(
            "[%s] 목표 리뷰 소스 %s건에 못 미칩니다 (블로그 %s건 + 카페글 %s건 = %s건 확보). "
            "모은 만큼만 사용해 계속 진행합니다.",
            place.name, MIN_REVIEW_SOURCES, len(blog_candidates), len(cafe_candidates), total_found
        )

    selected = ordered[:MAX_REVIEW_SOURCES]
    tier_counts = Counter(c["match_tier"] for c in selected)
    weak_used = tier_counts.get(3, 0)
    if signal_tiers and weak_used:
        logger.info(
            "   [매칭 정확도] %s -> 동네/지역/업종까지 일치하는 확실한 소스 %s건, "
            "장소명만 일치하는 소스로 %s건 보충했습니다.",
            place.name, len(selected) - weak_used, weak_used
        )

    return selected, refined_name_short


class GeminiCreditsDepleted(Exception):
    """Gemini 크레딧이 소진돼 이후 호출도 모두 실패하는 상태. 장소 데이터를 덮어쓰기 전에 중단합니다."""


def _analyze_or_stop(*args):
    ai_result = analyze_review(*args)
    if ai_result.get("credits_depleted"):
        raise GeminiCreditsDepleted()
    return ai_result


def _score_review_sources(place, candidates):
    """
    각 후보 글을 AI로 분석해 ad_probability(광고일 확률)와 has_place_info(장소에 대한
    실질적인 정보가 있는지)를 매깁니다. 기존에 저장된 ReviewSource와 (출처 종류, URL, 본문)이
    완전히 같은 후보는 재분석하지 않고 이전 판정을 재사용합니다 - 내용이 바뀌지 않은 글까지
    매번 Gemini에 다시 물어보는 비용을 줄입니다. 분석에 실패했던 글은 재사용하지 않고 다시
    분석합니다.
    """
    existing_by_key = {
        (rs.source_type, rs.url or "", rs.content_text): rs
        for rs in place.review_sources.filter(analysis_failed=False)
    }

    scored = []
    reused_count = 0
    for cand in candidates:
        key = (cand["source_type"], cand["url"] or "", cand["content"])
        existing = existing_by_key.get(key)

        if existing:
            is_ad = existing.is_ad
            ad_probability = existing.ad_probability
            has_place_info = existing.has_place_info
            is_review = existing.is_review
            exclude_reason = existing.exclude_reason
            analysis_failed = False
            reason = None
            reused_count += 1
        else:
            ai_result = _analyze_or_stop(cand["content"], place.name)
            analysis_failed = ai_result.get("analysis_failed", False)
            non_ad_probability = ai_result.get("non_ad_probability", 50)
            ad_probability = 100 - non_ad_probability
            is_ad = ai_result.get("is_ad", False)
            has_place_info = ai_result.get("has_place_info", True)
            is_review = ai_result.get("is_review", True)
            exclude_reason = ai_result.get("exclude_reason")
            reason = ai_result.get("reason", "분석 완료")

        scored.append({
            **cand,
            "is_ad": is_ad,
            "ad_probability": ad_probability,
            "has_place_info": has_place_info,
            "is_review": is_review,
            "exclude_reason": exclude_reason,
            "analysis_failed": analysis_failed,
            "reason": reason,
        })

    if reused_count:
        logger.info("   [AI 호출 절약] %s건은 이전과 동일한 글이라 재분석을 생략했습니다.", reused_count)

    return scored


def _extract_mood_keywords(place, scored):
    """
    [키워드 기반 장소 구분] 수집한 리뷰 소스들의 본문을 모아 분위기/특징 키워드를 AI로
    고릅니다. MOOD_KEYWORDS 목록에 없는 값은 여기서 한 번 더 걸러냅니다(이중 안전장치).

    리뷰 소스가 이전 실행과 완전히 동일해(전부 재사용됨, _score_review_sources 참고) 내용이
    바뀌지 않았다면, 이미 저장된 분위기 키워드를 그대로 두고 AI 호출을 생략합니다(비용 절약).

    [키워드 최신화 - 백필] 단, 이 장소에 분위기 키워드가 아직 하나도 없다면(이 기능이
    추가되기 전부터 있던 기존 장소가 여기 해당) 소스가 재사용되더라도 반드시 한 번은
    새로 뽑습니다 - 그렇지 않으면 리뷰 내용이 안 바뀌는 한 영영 채워지지 않습니다.
    """
    all_reused = bool(scored) and all(s["reason"] is None for s in scored)
    has_existing_mood_keywords = place.keywords.filter(keyword_type='mood').exists()
    if all_reused and has_existing_mood_keywords:
        logger.info("   [AI 호출 절약] 리뷰 소스가 이전과 동일해 분위기 키워드 재분석도 생략했습니다.")
        return

    combined_content = "\n\n".join(s["content"] for s in scored)
    raw_keywords = extract_mood_keywords(place.name, combined_content, MOOD_KEYWORDS)

    allowed = set(MOOD_KEYWORDS)
    valid_keywords = [k for k in raw_keywords if k in allowed]
    if raw_keywords and len(valid_keywords) != len(raw_keywords):
        logger.warning(
            "   [분위기 키워드 필터링] AI가 후보 목록 밖의 값을 반환해 걸러냈습니다: %s",
            [k for k in raw_keywords if k not in allowed]
        )
    valid_keywords = list(dict.fromkeys(valid_keywords))[:MAX_MOOD_KEYWORDS_PER_PLACE]

    place.keywords.filter(keyword_type='mood').delete()
    if valid_keywords:
        PlaceKeyword.objects.bulk_create([
            PlaceKeyword(place=place, keyword_type='mood', keyword=k) for k in valid_keywords
        ])
    logger.info("   [분위기 키워드] %s -> %s", place.name, valid_keywords or '(없음)')


def _save_fallback_placeholder(place, default_user, no_sources_reason):
    """
    [공용 placeholder 처리] 후보 글을 하나도 못 찾았거나(전체 개수 0건), 후보는 있었지만
    전부 그 장소에 대한 실질적인 정보가 없다고 판정된 경우(has_place_info=False뿐) 모두
    같은 방식으로 처리합니다: 안내용 placeholder 리뷰를 넣고 기존 리뷰 소스/분위기
    키워드는 비웁니다. no_sources_reason은 로그에만 쓰이는 상황 설명입니다.
    """
    fallback_content = "네이버 등록 인증 업체 정보입니다."
    ai_result = _analyze_or_stop(fallback_content)
    non_ad_probability = ai_result.get("non_ad_probability", 50)
    ad_probability = 100 - non_ad_probability

    Review.objects.update_or_create(
        place=place, user=default_user,
        defaults={'content': fallback_content, 'hashtags': '', 'rating': 5}
    )
    PlaceAnalysis.objects.update_or_create(
        name=place.name,
        defaults={
            'content_text': fallback_content,
            'is_ad': ai_result.get('is_ad', False),
            'ad_probability': ad_probability,
            'ai_summary': ai_result.get('reason', '분석할 리뷰를 찾지 못함'),
        }
    )
    place.review_sources.all().delete()
    place.keywords.filter(keyword_type='mood').delete()  # 분석할 내용이 없으니 분위기 키워드도 비웁니다.
    logger.info(
        "   [DB 저장 완료] %s -> %s, 기본값으로 처리 (비광고 확률 %s%%)",
        place.name, no_sources_reason, non_ad_probability
    )


def _save_review_sources(place, sources):
    ReviewSource.objects.bulk_create([
        ReviewSource(
            place=place,
            source_type=s["source_type"],
            title=s["title"][:255],
            url=s["url"] or None,
            content_text=s["content"],
            is_ad=s["is_ad"],
            ad_probability=s["ad_probability"],
            has_place_info=s.get("has_place_info", True),
            is_review=s.get("is_review", True),
            exclude_reason=s.get("exclude_reason"),
            analysis_failed=s.get("analysis_failed", False),
        )
        for s in sources
    ])


def _refresh_place_reviews(place, headers, default_user, request_interval):
    """
    [리뷰 최신화 로직 - 장소 정보 수집과 완전히 분리] 장소 하나에 대해 블로그+카페글에서
    최소 MIN_REVIEW_SOURCES건(가능한 만큼)의 글을 모아 각각 AI로 광고 여부를 분석하고,
    평균 광고 확률로 PlaceAnalysis를 갱신합니다. 화면에 노출되는 대표 Review는 평균에
    가장 가까운 점수를 받은 글 1건으로 정합니다(수집한 소스 전체를 리뷰 목록에 그대로
    올리지 않습니다). 수집한 소스 전체는 ReviewSource 테이블에 교체 저장됩니다.

    [키워드 최신화] 위치/종류 키워드도 매번 다시 계산합니다(비용 없음) - 이 기능이 추가되기
    전부터 있던 기존 장소를 백필하는 역할도 겸합니다(_store_structural_keywords 참고).

    [오탐 매칭 완화 2단계 - 정보성 필터링] 장소명(+지역/업종)이 실제로 언급됐어도 그
    장소에 대한 알맹이 있는 내용이 없는 글(예: 스치듯 이름만 언급, 목록형 나열글)은
    _score_review_sources()가 매긴 has_place_info=False를 기준으로 걸러내고, 평균 광고
    확률/대표 리뷰 선정/분위기 키워드 분석 어디에도 반영하지 않습니다.

    [리뷰 필터링] 구인공고/무관한 글/상업적 공고(is_review=False)도 같은 계산에서 제외합니다.
    NON_REVIEW_SIGNAL_PATTERNS(1차 고정 문구 필터)를 빠져나간 글을 잡는 2차 안전장치입니다.
    이 글들은 판정 검토와 재분석 생략을 위해 ReviewSource에는 저장합니다.
    """
    _store_structural_keywords(place)

    candidates, refined_name_short = _collect_review_source_candidates(place, headers, request_interval)

    if not candidates:
        # 후보 글을 하나도 못 찾은 경우: 안내용 placeholder로 처리합니다.
        _save_fallback_placeholder(place, default_user, "리뷰 소스 없음")
        return

    scored_all = _score_review_sources(place, candidates)
    non_reviews = [s for s in scored_all if not s.get("is_review", True)]
    if non_reviews:
        reason_counts = Counter(s.get("exclude_reason") or "other_notice" for s in non_reviews)
        logger.info(
            "   [리뷰 필터링] %s -> 구인공고 %s건 / 무관한 글 %s건 / 기타 공고 %s건을 제외했습니다.",
            place.name, reason_counts["job_posting"], reason_counts["unrelated"], reason_counts["other_notice"]
        )

    reviews = [s for s in scored_all if s.get("is_review", True)]
    scored = [s for s in reviews if s.get("has_place_info", True)]
    dropped_count = len(reviews) - len(scored)
    if dropped_count:
        logger.info(
            "   [정보성 필터링] %s -> 장소명은 언급됐지만 실질적인 정보가 없다고 판단된 글 %s건을 제외했습니다.",
            place.name, dropped_count
        )

    if not scored:
        # 후보는 있었지만 전부 "이름만 스치듯 언급"으로 판정된 경우: 후보가 아예 없던
        # 경우와 동일하게 placeholder로 처리합니다.
        _save_fallback_placeholder(place, default_user, "장소 정보가 있는 리뷰 소스 없음")
        _save_review_sources(place, non_reviews)
        return

    # 분석에 실패한 글의 기본값(50%)이 평균을 끌어당기지 않도록 정상 판정만 계산에 씁니다.
    # 전부 실패했으면 기존처럼 기본값으로 저장하고 다음 수집 때 재분석합니다.
    judged = [s for s in scored if not s.get("analysis_failed")] or scored
    avg_ad_probability = round(sum(s["ad_probability"] for s in judged) / len(judged))
    ad_threshold = getattr(settings, 'AD_EXCLUDE_THRESHOLD', 70)
    final_is_ad = avg_ad_probability >= ad_threshold

    # [평균에 가장 가까운 대표 리뷰] 여러 값이 동일하게 가까우면 먼저 나온 항목을 사용합니다.
    representative = min(judged, key=lambda s: abs(s["ad_probability"] - avg_ad_probability))

    all_tags = []
    for s in scored:
        all_tags.extend(re.findall(r'#[가-힣a-zA-Z0-9_]+', s["content"]))
    unique_tags = list(dict.fromkeys(all_tags))[:5]
    if not unique_tags:
        unique_tags = [f"#{refined_name_short.replace(' ', '')}"] if refined_name_short else []
    tags_string = ", ".join(unique_tags)

    representative_reason = representative.get("reason") or "이전 분석 결과 재사용"
    ai_summary = (
        f"총 {len(judged)}건의 블로그/카페글을 분석한 평균 광고 확률 {avg_ad_probability}%입니다. "
        f"(대표 리뷰 사유: {representative_reason})"
    )

    Review.objects.update_or_create(
        place=place, user=default_user,
        defaults={'content': representative["content"], 'hashtags': tags_string, 'rating': 5}
    )

    PlaceAnalysis.objects.update_or_create(
        name=place.name,
        defaults={
            'content_text': representative["content"][:2000],
            'is_ad': final_is_ad,
            'ad_probability': avg_ad_probability,
            'ai_summary': ai_summary,
        }
    )

    place.review_sources.all().delete()
    _save_review_sources(place, scored + non_reviews)

    _extract_mood_keywords(place, scored)

    logger.info(
        "   [DB 저장 완료] %s -> 글 %s건 평균 비광고 확률 %s%% (대표 리뷰 1건 노출)",
        place.name, len(scored), 100 - avg_ad_probability
    )


def refresh_existing_places(request_interval=0.2, only_new=False, only_failed=False):
    """
    [리뷰 최신화 로직 - 장소 수집과 분리] 새로 장소를 찾지 않고(지역 검색 API 호출 없음),
    DB에 이미 등록된 장소들의 리뷰만 블로그+카페글에서 모아 평균 광고 확률로 갱신합니다.
    cron 등으로 주기적으로 실행하면 지역 검색 API 호출(과금) 없이도 리뷰/광고판별 결과를
    최신 상태로 유지할 수 있습니다.

    only_new=True면 아직 한 번도 리뷰가 분석되지 않은(PlaceAnalysis가 없는) 장소만
    대상으로 합니다 - mine_naver로 새로 등록한 장소의 리뷰를 처음 채울 때 사용하세요.
    (관리 명령: python manage.py refresh_naver [--only-new])

    only_failed=True면 AI 분석 실패 기록이 남은 장소만 대상으로 합니다. Gemini 크레딧이
    소진되면 그 장소의 기존 데이터를 그대로 두고 즉시 중단하므로, 충전 후 다시 실행하면
    남은 장소부터 이어집니다. (관리 명령: python manage.py refresh_naver --only-failed)
    """
    headers = _get_naver_headers()
    if not headers:
        logger.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET가 .env에 설정되어 있지 않습니다.")
        return

    default_user = _get_default_user()
    if not default_user:
        logger.error("DB에 등록된 사용자가 없습니다. 먼저 계정을 하나 생성해주세요.")
        return

    if only_new:
        analyzed_names = set(PlaceAnalysis.objects.values_list('name', flat=True))
        places = [p for p in Place.objects.all() if p.name not in analyzed_names]
    elif only_failed:
        failed_names = PlaceAnalysis.objects.filter(
            ai_summary__contains='AI 연동 오류'
        ).values_list('name', flat=True)
        places = list(Place.objects.filter(
            Q(review_sources__analysis_failed=True) | Q(name__in=failed_names)
        ).distinct())
    else:
        places = list(Place.objects.all())

    logger.info(
        "기존 장소 %s건의 리뷰 최신화를 시작합니다%s.",
        len(places), " (아직 분석되지 않은 장소만)" if only_new else ""
    )

    updated = 0
    for place in places:
        try:
            _refresh_place_reviews(place, headers, default_user, request_interval)
            updated += 1
        except GeminiCreditsDepleted:
            logger.error(
                "Gemini 크레딧이 소진되어 중단합니다 (%s/%s건 처리). 충전 후 다시 실행하세요.",
                updated, len(places)
            )
            raise
        except Exception:
            logger.exception("리뷰 최신화 중 오류 발생, 건너뜁니다: %s", place.name)
        time.sleep(request_interval)
