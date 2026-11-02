import json
import os

from django.core.management.base import BaseCommand

from api.models import Place, ReviewSource


class Command(BaseCommand):
    """
    [자체 학습 데이터셋 구축 - 1단계: 레이블 축적] admin에서 사람이 검토/확정한 레이블만
    모아 학습용 데이터셋 파일(jsonl)로 내보냅니다. AI가 예측한 값(is_ad, PlaceKeyword 생성
    결과)이 아니라, ReviewSourceAdmin/PlaceKeywordAdmin의 "검증" 액션으로 사람이 직접
    확정한 값만 사용합니다 - 즉 admin에서 검토를 많이 할수록 여기서 뽑히는 데이터셋도
    함께 커집니다.

    지금 당장은 파인튜닝을 실행하는 명령이 아니라, 파인튜닝/자체 분류기 학습에 쓸 수 있는
    "정답이 확실한 데이터"를 파일로 모아두는 단계입니다. (다음 단계: 평가셋 분리 → 이 데이터로
    프롬프트 개선/소형 분류기 학습 실험)

    사용법:
        python manage.py export_training_data
        python manage.py export_training_data --output-dir my_dir

    출력:
        <output-dir>/ad_detection_dataset.jsonl
            광고 탐지용. 한 줄 = 리뷰 소스 1건.
            {"text": ..., "label": "ad"|"not_ad", "place": ..., "source_type": ..., "url": ...}

        <output-dir>/mood_keywords_dataset.jsonl
            분위기 키워드용. 한 줄 = 장소 1곳 (검증된 mood 키워드가 하나라도 있는 장소만).
            {"place": ..., "text": ..., "correct_keywords": [...], "incorrect_keywords": [...]}
    """

    help = "admin에서 검증(확정)한 레이블을 모아 학습용 데이터셋(jsonl)으로 내보냅니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', type=str, default='training_data',
            help='데이터셋 파일을 저장할 디렉토리 (기본: training_data)',
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)

        ad_path, ad_count = self._export_ad_detection_dataset(output_dir)
        mood_path, mood_count = self._export_mood_keywords_dataset(output_dir)

        self.stdout.write(self.style.SUCCESS(
            f"완료:\n"
            f"  - 광고 탐지 데이터셋: {ad_path} ({ad_count}건)\n"
            f"  - 분위기 키워드 데이터셋: {mood_path} ({mood_count}건)"
        ))
        if ad_count == 0 and mood_count == 0:
            self.stdout.write(self.style.WARNING(
                "검증된 레이블이 아직 없습니다. admin에서 ReviewSource/PlaceKeyword 목록을 "
                "확인하고 '검증' 액션으로 정답을 확정해주세요."
            ))

    def _export_ad_detection_dataset(self, output_dir):
        path = os.path.join(output_dir, 'ad_detection_dataset.jsonl')
        verified_sources = ReviewSource.objects.filter(
            is_ad_verified=True, verified_is_ad__isnull=False, is_review=True
        ).select_related('place')

        count = 0
        with open(path, 'w', encoding='utf-8') as f:
            for source in verified_sources:
                row = {
                    'text': source.content_text,
                    'label': 'ad' if source.verified_is_ad else 'not_ad',
                    'place': source.place.name,
                    'source_type': source.source_type,
                    'url': source.url,
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                count += 1

        return path, count

    def _export_mood_keywords_dataset(self, output_dir):
        path = os.path.join(output_dir, 'mood_keywords_dataset.jsonl')

        # place별로 검증(verified가 True/False로 확정)된 mood 키워드가 하나라도 있는 곳만
        # 모아, 맞는 키워드/틀린 키워드를 함께 기록합니다(틀린 키워드는 향후 다중 레이블
        # 분류기를 학습할 때 negative 예시로 사용).
        places_with_reviewed_mood = Place.objects.filter(
            keywords__keyword_type='mood', keywords__verified__isnull=False
        ).distinct()

        count = 0
        with open(path, 'w', encoding='utf-8') as f:
            for place in places_with_reviewed_mood:
                mood_qs = place.keywords.filter(keyword_type='mood', verified__isnull=False)
                correct_keywords = list(mood_qs.filter(verified=True).values_list('keyword', flat=True))
                incorrect_keywords = list(mood_qs.filter(verified=False).values_list('keyword', flat=True))
                combined_content = "\n\n".join(
                    place.review_sources.filter(is_review=True).values_list('content_text', flat=True)
                )
                row = {
                    'place': place.name,
                    'text': combined_content,
                    'correct_keywords': correct_keywords,
                    'incorrect_keywords': incorrect_keywords,
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                count += 1

        return path, count
