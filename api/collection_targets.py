"""
[DB 자동 축적 - 1단계: 장소 x 키워드 조합]
작업 스케줄러(또는 터미널)에 검색어를 하나씩 직접 입력하는 대신, 여기 정의해둔 장소
리스트 x 키워드 리스트를 조합해 검색어를 자동으로 만듭니다 (예: "대전 둔산동
베이커리카페"). api/management/commands/auto_collect.py가 이 모듈의
build_combinations()를 사용해 api.naver_miner.auto_collect_from_targets()에 넘깁니다.

[프로토타입 범위 제한]
지금은 프로토타입 단계라 조합이 폭발적으로 늘어나지 않도록 동네/키워드 범위를 의도적으로
좁게 잡았습니다. 범위를 넓히고 싶으면 아래 PLACES/KEYWORDS만 수정하면 됩니다 - 코드
다른 곳(auto_collect 커맨드, naver_miner.py)은 건드릴 필요 없습니다.

[수식어 리스트는 1차 구현에서 보류]
"분위기 좋은", "감성" 같은 수식어를 추가로 조합하는 기능은 보류했습니다. 나중에
추가하려면:
1. 아래에 MODIFIERS = ["분위기 좋은", "감성", ...] 리스트를 만들고
2. build_combinations()에 modifiers 인자를 추가해 PLACES x KEYWORDS x MODIFIERS
   3중 조합(예: "대전 둔산동 분위기 좋은 베이커리카페")을 만들도록 반복문 한 겹만
   더 넣으면 됩니다. 조합 수가 (장소 수 x 키워드 수 x 수식어 수)로 곱해져 빠르게
   커지니, 처음엔 수식어도 1~2개로 좁게 시작하는 걸 권장합니다.
"""

REGION_PREFIX = "대전"

# 프로토타입 대상 동네. 범위를 넓히려면 여기에 추가하세요.
PLACES = [
    "봉명동",
    "도안동",
    "둔산동",
    "궁동",
    "은행동",
    "탄방동",
    "노은동",
    "대흥동",
]

# 카페/식당/술집 상위 분류 자체는 검색어로 쓰지 않습니다(너무 포괄적이라 결과 품질이
# 떨어짐) - 아래 하위 키워드만 실제 조합에 사용합니다 (flat_keywords() 참고). 위 계층
# 구조는 리포트/확인용으로만 남겨둡니다.
KEYWORDS = {
    "카페": ["베이커리카페", "디저트카페"],
    "식당": ["한식", "양식", "일식", "중식"],
    "술집": ["칵테일", "포차", "와인"],
}


def flat_keywords():
    """KEYWORDS에 속한 모든 하위 키워드를 하나의 평평한 리스트로 펼칩니다."""
    result = []
    for sub_keywords in KEYWORDS.values():
        result.extend(sub_keywords)
    return result


def build_combinations(places=None, keywords=None):
    """
    장소 리스트 x 키워드 리스트를 조합해 네이버 지역 검색에 쓸 검색어 문자열 목록을
    만듭니다. 예: "대전 둔산동 베이커리카페". places/keywords를 넘기면 기본값(PLACES/
    flat_keywords()) 대신 그 값만 사용합니다(auto_collect 커맨드의 --places/--keywords
    옵션이 이렇게 부분 실행할 때 씁니다). 빈 리스트를 넘기면 기본값을 쓴 것으로 취급합니다.
    """
    target_places = places if places else PLACES
    target_keywords = keywords if keywords else flat_keywords()
    return [
        f"{REGION_PREFIX} {place} {keyword}".strip()
        for place in target_places
        for keyword in target_keywords
    ]
