import json
import os
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from api.models import Place, PlaceViewLog, SearchLog
from api.recommendation import (
    VIEW_WEIGHT, SEARCH_WEIGHT, RECENT_SEARCH_LIMIT, RECENT_VIEW_LIMIT,
    find_matching_places,
)

User = get_user_model()


class Command(BaseCommand):
    """
    [추천용 데이터셋 구축] 지금까지 쌓인 사용자 행동 로그(SearchLog/PlaceViewLog)를
    "사용자-장소 상호작용" 데이터셋으로 정리해 내보냅니다. 지금 서비스에서 실제로
    동작하는 추천(api/recommendation.py)은 이 데이터를 즉석에서 계산해 쓰는 규칙 기반
    베이스라인이라 이 명령이 없어도 됩니다. 이 명령이 필요한 이유는 원 요구사항(SFR-007)이
    명시한 Neural CF 같은 학습 기반 모델을 나중에 실제로 학습시키려면, "이 사용자가 이
    장소와 얼마나 상호작용했는가"를 정리한 학습용 데이터셋이 별도로 있어야 하기 때문입니다
    - 지금까지는 이 파이프라인 자체가 없었습니다.

    [상호작용을 만드는 두 가지 신호]
    - PlaceViewLog(강한 신호): 사용자가 실제로 눌러서 상세 페이지를 연 장소. 1건당
      VIEW_WEIGHT(api/recommendation.py, 기본 3)만큼 반영합니다.
    - SearchLog(약한 신호): 사용자가 검색한 키워드로 실제 어떤 장소들이 검색 결과에
      노출됐는지를 find_matching_places()(SearchView가 쓰는 것과 동일한 함수)로
      재구성합니다. 노출된 장소 1건당 SEARCH_WEIGHT(기본 1)만큼 반영합니다 - "클릭"이
      아니라 "노출"이므로 조회보다 약한 신호로 취급합니다.

    같은 (사용자, 장소) 쌍에 여러 신호가 겹치면 합산해서 하나의 상호작용 세기(weight)로
    만듭니다. 이 값 자체가 정답 레이블은 아니고, Neural CF 등에서 암묵적 피드백(implicit
    feedback)의 강도로 흔히 쓰는 형태입니다.

    사용법:
        python manage.py export_recommendation_dataset
        python manage.py export_recommendation_dataset --output-dir my_dir

    출력:
        <output-dir>/interactions.jsonl
            한 줄 = (사용자, 장소) 상호작용 1건.
            {"user_id":, "username":, "place_id":, "place_name":, "view_count":,
             "search_match_count":, "weight":, "last_interaction_at": ISO8601}

        <output-dir>/place_features.jsonl
            한 줄 = 장소 1곳의 특징(콘텐츠 기반/하이브리드 모델에 쓸 수 있는 부가 정보).
            {"place_id":, "name":, "location_keywords": [...], "category_keywords": [...],
             "mood_keywords": [...]}
    """

    help = "SearchLog/PlaceViewLog를 사용자-장소 상호작용 데이터셋(jsonl)으로 내보냅니다 (추천 모델 학습용)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', type=str, default='training_data',
            help='데이터셋 파일을 저장할 디렉토리 (기본: training_data)',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)

        interactions_path, interaction_count, user_count = self._export_interactions(output_dir)
        features_path, place_count = self._export_place_features(output_dir)

        self.stdout.write(self.style.SUCCESS(
            f"완료:\n"
            f"  - 상호작용 데이터셋: {interactions_path} ({interaction_count}건, 사용자 {user_count}명)\n"
            f"  - 장소 특징 데이터셋: {features_path} ({place_count}건)"
        ))
        if interaction_count == 0:
            self.stdout.write(self.style.WARNING(
                "상호작용 기록이 아직 없습니다. 검색/조회 기록이 쌓인 뒤 다시 실행해주세요."
            ))

    def _build_interaction_counts(self, user):
        """
        [상호작용 집계] 사용자 한 명에 대해 (place_id -> (view_count, search_match_count))를
        계산합니다. RECENT_VIEW_LIMIT/RECENT_SEARCH_LIMIT는 recommendation.py와 동일한
        상한을 재사용해, 실시간 추천 스코어링이 보는 범위와 이 데이터셋이 어긋나지
        않도록 합니다.
        """
        view_counts = Counter(
            PlaceViewLog.objects.filter(user=user).order_by('-created_at')
            .values_list('place_id', flat=True)[:RECENT_VIEW_LIMIT]
        )

        search_match_counts = Counter()
        recent_searches = list(
            SearchLog.objects.filter(user=user).order_by('-created_at')
            .values_list('keyword', flat=True)[:RECENT_SEARCH_LIMIT]
        )
        for keyword in recent_searches:
            for place_id in find_matching_places(keyword).values_list('id', flat=True):
                search_match_counts[place_id] += 1

        return view_counts, search_match_counts

    def _export_interactions(self, output_dir):
        path = os.path.join(output_dir, 'interactions.jsonl')

        user_ids = set(SearchLog.objects.values_list('user_id', flat=True).distinct())
        user_ids |= set(PlaceViewLog.objects.values_list('user_id', flat=True).distinct())

        interaction_count = 0
        active_user_count = 0
        with open(path, 'w', encoding='utf-8') as f:
            for user_id in sorted(user_ids):
                user = self._get_user(user_id)
                if not user:
                    continue

                view_counts, search_match_counts = self._build_interaction_counts(user)
                place_ids = set(view_counts) | set(search_match_counts)
                if not place_ids:
                    continue
                active_user_count += 1

                places_by_id = {p.id: p for p in Place.objects.filter(id__in=place_ids)}
                last_interaction_by_place = self._last_interaction_timestamps(user, place_ids)

                for place_id in place_ids:
                    place = places_by_id.get(place_id)
                    if not place:
                        continue  # 상호작용 이후 삭제된 장소일 수 있음
                    view_count = view_counts.get(place_id, 0)
                    search_match_count = search_match_counts.get(place_id, 0)
                    weight = view_count * VIEW_WEIGHT + search_match_count * SEARCH_WEIGHT

                    row = {
                        'user_id': user.id,
                        'username': user.username,
                        'place_id': place.id,
                        'place_name': place.name,
                        'view_count': view_count,
                        'search_match_count': search_match_count,
                        'weight': weight,
                        'last_interaction_at': last_interaction_by_place.get(place_id),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                    interaction_count += 1

        return path, interaction_count, active_user_count

    def _last_interaction_timestamps(self, user, place_ids):
        """(사용자, 장소)별 가장 최근 상호작용 시각 - 조회 기록이 있으면 그 시각, 없으면 None."""
        timestamps = {}
        for place_id, created_at in (
            PlaceViewLog.objects.filter(user=user, place_id__in=place_ids)
            .order_by('place_id', '-created_at')
            .values_list('place_id', 'created_at')
        ):
            if place_id not in timestamps:
                timestamps[place_id] = created_at.isoformat()
        return timestamps

    def _get_user(self, user_id):
        return User.objects.filter(id=user_id).first()

    def _export_place_features(self, output_dir):
        path = os.path.join(output_dir, 'place_features.jsonl')

        count = 0
        with open(path, 'w', encoding='utf-8') as f:
            for place in Place.objects.all():
                kws = list(place.keywords.values('keyword_type', 'keyword'))
                row = {
                    'place_id': place.id,
                    'name': place.name,
                    'location_keywords': [k['keyword'] for k in kws if k['keyword_type'] == 'location'],
                    'category_keywords': [k['keyword'] for k in kws if k['keyword_type'] == 'category'],
                    'mood_keywords': [k['keyword'] for k in kws if k['keyword_type'] == 'mood'],
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                count += 1

        return path, count
