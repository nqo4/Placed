from django.core.management.base import BaseCommand, CommandError

from api.naver_miner import DEFAULT_MAX_PLACES_PER_KEYWORD, mine_from_naver


class Command(BaseCommand):
    """
    [자동화 + 로직 분리] 여러 키워드를 한 번에 넘길 수 있습니다. 이 명령은 장소 정보
    (이름/주소/설명/사진)만 수집합니다 - 리뷰나 광고 판별은 하지 않습니다(자세한 내용은
    api/naver_miner.py 상단 설명 참고).

    사용법:
        python manage.py mine_naver "대전 유성구 맛집"
        python manage.py mine_naver "대전 유성구 맛집" "대전 중구 카페" "대전 대덕구 국밥"
        python manage.py mine_naver "대전 유성구 맛집" --interval 0.5
        python manage.py mine_naver "대전 유성구 맛집" --limit 50

    이 명령이 끝난 뒤, 새로 등록된 장소의 리뷰(블로그+카페글 평균 광고 확률)까지 채우려면
    이어서 아래 명령을 실행하세요:
        python manage.py refresh_naver --only-new

    이미 등록된 장소의 리뷰만 새로 고치고 싶다면(신규 장소를 찾지 않음) 대신
    `python manage.py refresh_naver` 를 사용하세요.
    """

    help = "Naver 지역 검색 API로 장소 정보(이름/주소/사진)만 수집합니다. 리뷰 수집은 refresh_naver를 따로 실행하세요."

    def add_arguments(self, parser):
        parser.add_argument('keywords', nargs='+', type=str, help='수집할 검색 키워드 (여러 개 가능)')
        parser.add_argument(
            '--interval', type=float, default=0.2,
            help='Naver API 과다 호출(429)을 피하기 위한 요청 간 최소 대기 시간(초). 기본 0.2초.'
        )
        parser.add_argument(
            '--limit', type=int, default=DEFAULT_MAX_PLACES_PER_KEYWORD,
            help=(
                '키워드 1개당 수집할 최대 장소 수 (기본 %(default)s건). 네이버 지역 검색 API는 '
                '한 번에 5건까지만 주기 때문에, 내부적으로 여러 페이지를 이어서 이 개수를 채웁니다.'
            )
        )

    def handle(self, *args, **options):
        keywords = [k.strip() for k in options['keywords'] if k.strip()]
        if not keywords:
            raise CommandError('최소 한 개 이상의 검색 키워드를 입력해주세요.')
        if options['limit'] <= 0:
            raise CommandError('--limit 은 1 이상이어야 합니다.')

        self.stdout.write(self.style.NOTICE(
            f"[mine_naver] {len(keywords)}개 키워드 수집을 시작합니다 (키워드당 최대 {options['limit']}건): {keywords}"
        ))
        mine_from_naver(keywords, request_interval=options['interval'], max_places_per_keyword=options['limit'])
        self.stdout.write(self.style.SUCCESS('[mine_naver] 완료.'))
