from django.core.management.base import BaseCommand, CommandError

from api.naver_miner import GeminiCreditsDepleted, MIN_REVIEW_SOURCES, refresh_existing_places


class Command(BaseCommand):
    """
    [자동화 + 리뷰만 최신화] DB에 이미 등록된 장소를 새로 검색하지 않고(Local API 미호출),
    각 장소마다 블로그+카페글에서 최소 %(min_sources)s건(가능한 만큼)을 모아 개별 분석한 뒤
    그 평균 광고 확률로 리뷰를 최신화합니다. 이 명령을 cron/작업 스케줄러에 주기적으로
    등록해두면 지역 검색 API 호출량을 늘리지 않으면서 리뷰·광고 판별 결과를 최신 상태로
    유지할 수 있습니다.

    사용법:
        python manage.py refresh_naver
        python manage.py refresh_naver --interval 0.5

    mine_naver로 새로 등록한 장소는 리뷰가 아직 비어 있습니다. 신규 장소의 리뷰만 처음
    채우고 싶다면(이미 분석된 기존 장소는 건드리지 않음) --only-new 를 사용하세요:
        python manage.py refresh_naver --only-new

    예) 매일 새벽 3시에 실행하는 cron 등록 (Linux/서버):
        0 3 * * * cd /path/to/project && /path/to/venv/bin/python manage.py refresh_naver >> refresh_naver.log 2>&1
    """ % {'min_sources': MIN_REVIEW_SOURCES}

    help = "이미 등록된 장소들의 리뷰/광고판별 결과를 블로그+카페글 여러 건의 평균으로 갱신합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval', type=float, default=0.2,
            help='Naver API 과다 호출(429)을 피하기 위한 요청 간 최소 대기 시간(초). 기본 0.2초.'
        )
        parser.add_argument(
            '--only-new', action='store_true',
            help='아직 한 번도 리뷰가 분석되지 않은(PlaceAnalysis가 없는) 장소만 대상으로 합니다. '
                 'mine_naver 직후 신규 장소 리뷰만 채울 때 사용하세요.'
        )
        parser.add_argument(
            '--only-failed', action='store_true',
            help='AI 분석 실패 기록이 남은 장소만 다시 분석합니다. 크레딧이 소진되면 즉시 중단합니다.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('[refresh_naver] 장소 리뷰 최신화를 시작합니다...'))
        try:
            refresh_existing_places(
                request_interval=options['interval'],
                only_new=options['only_new'],
                only_failed=options['only_failed'],
            )
        except GeminiCreditsDepleted:
            raise CommandError('Gemini 크레딧이 소진되어 중단했습니다. 충전 후 다시 실행하세요.')
        self.stdout.write(self.style.SUCCESS('[refresh_naver] 완료.'))
