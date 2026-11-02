from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Place, PlaceAnalysis


class Command(BaseCommand):
    """
    [기존 스크래핑 데이터 폐기] mine_naver/auto_collect로 쌓아온 장소 데이터를 전부
    지우고, 개선된 이미지 검색 로직(region_hint + filter=large, api/naver_miner.py
    참고)으로 처음부터 다시 수집하기 위한 명령입니다.

    Place를 지우면 CASCADE로 PlaceImage(사진)/ReviewSource(리뷰 원본)/
    PlaceKeyword(위치·종류·분위기 태그)/Review(대표 리뷰)/PlaceViewLog(조회 기록)도
    함께 삭제됩니다. PlaceAnalysis는 Place와 FK로 연결돼 있지 않고 장소 이름(name)
    문자열로만 매칭되므로(api/views.py의 SearchView 참고) Place 삭제만으로는 지워지지
    않습니다 - 그대로 두면 나중에 같은 이름으로 다시 등록되는 장소가 옛 광고 판별
    결과를 그대로 재사용하게 되므로 여기서 함께 지웁니다.

    User(계정), SearchLog(검색 기록) 등 사용자 관련 데이터는 건드리지 않습니다.

    사용법:
        python manage.py reset_places --dry-run   # 지워질 건수만 미리 확인 (삭제 안 함)
        python manage.py reset_places             # 확인 메시지 뜨면 yes 입력 후 삭제
        python manage.py reset_places --yes       # 확인 없이 바로 삭제 (스크립트/CI용)

    삭제 후 다시 수집하려면:
        python manage.py auto_collect
        python manage.py refresh_naver --only-new
    """

    help = "기존에 수집된 장소/사진/리뷰/분석 데이터를 전부 삭제합니다 (사용자 계정/검색 기록은 유지)."

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='확인 없이 즉시 삭제합니다.')
        parser.add_argument('--dry-run', action='store_true', help='삭제하지 않고 지워질 건수만 보여줍니다.')

    def handle(self, *args, **options):
        place_count = Place.objects.count()
        analysis_count = PlaceAnalysis.objects.count()

        self.stdout.write(self.style.NOTICE(
            f"[reset_places] 삭제 대상: Place {place_count}건 "
            f"(+ 연결된 사진/리뷰/키워드/조회기록은 CASCADE로 함께 삭제), "
            f"PlaceAnalysis(광고 판별 캐시) {analysis_count}건"
        ))

        if place_count == 0 and analysis_count == 0:
            self.stdout.write(self.style.SUCCESS("[reset_places] 이미 비어 있습니다. 할 일이 없습니다."))
            return

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE("(dry-run이라 실제로 삭제하지 않았습니다.)"))
            return

        if not options['yes']:
            answer = input(
                "정말로 위 데이터를 전부 삭제하시겠습니까? 되돌릴 수 없습니다. (yes 입력 시 진행): "
            )
            if answer.strip().lower() != 'yes':
                self.stdout.write(self.style.WARNING("취소했습니다. 아무 것도 삭제하지 않았습니다."))
                return

        with transaction.atomic():
            deleted_places_total, _ = Place.objects.all().delete()
            deleted_analysis_total, _ = PlaceAnalysis.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f"[reset_places] 완료. Place 및 연결 데이터 {deleted_places_total}건, "
            f"PlaceAnalysis {deleted_analysis_total}건을 삭제했습니다. "
            f"이제 `python manage.py auto_collect` 로 새로 수집을 시작하세요."
        ))
