from django.core.management.base import BaseCommand, CommandError

from api.collection_targets import PLACES, build_combinations, flat_keywords
from api.naver_miner import AUTO_COLLECT_DEFAULT_PER_COMBO, auto_collect_from_targets


class Command(BaseCommand):
    """
    [DB 자동 축적] api/collection_targets.py에 미리 정의해둔 장소 리스트 x 키워드
    리스트를 조합해 검색어를 자동으로 만들고(예: "대전 둔산동 베이커리카페"), 조합별로
    "신규" 장소가 --per-combo건 쌓일 때까지 네이버 지역 검색을 반복합니다.

    이미 등록된 장소(상호명+주소 일치) 또는 이번 실행에서 이미 처리한 장소는 목표
    건수에 포함되지 않습니다. 지역 검색 페이지네이션이 더 이상 새 결과를 주지 않거나
    안전장치(페이지/시간 상한, api/naver_miner.py의 AUTO_COLLECT_MAX_PAGES_PER_COMBO /
    AUTO_COLLECT_MAX_SECONDS_PER_COMBO)에 걸리면, 그 조합은 목표에 못 미치더라도
    "더 이상 불러올 장소가 없다"고 보고 중단한 뒤 다음 조합으로 넘어갑니다.

    수식어(분위기 좋은, 감성 등) 리스트는 이번 1차 구현에서는 보류했습니다 - 범위를 더
    넓히거나 수식어를 추가하고 싶으면 api/collection_targets.py만 수정하면 됩니다.

    사용법:
        python manage.py auto_collect
        python manage.py auto_collect --per-combo 5
        python manage.py auto_collect --places 둔산동 봉명동 --keywords 한식 디저트카페
        python manage.py auto_collect --dry-run

    이 명령은 mine_naver와 마찬가지로 장소 정보(이름/주소/사진)만 수집합니다. 새로
    등록된 장소의 리뷰까지 채우려면 이어서 실행하세요:
        python manage.py refresh_naver --only-new

    [스케줄링] 이 명령을 Windows 작업 스케줄러 등에 등록하는 건, 아래처럼 --dry-run과
    소규모 --per-combo로 먼저 몇 번 직접 실행해서 의도대로 동작하는 걸 확인한 뒤에
    하는 걸 권장합니다:
        python manage.py auto_collect --dry-run
        python manage.py auto_collect --places 둔산동 --keywords 한식 --per-combo 3
    """

    help = "미리 정의된 장소x키워드 조합으로 신규 장소를 목표 건수만큼 자동 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-combo', type=int, default=AUTO_COLLECT_DEFAULT_PER_COMBO,
            help=(
                '조합 1개당 목표로 하는 "신규" 장소 수 (기본 %(default)s건). 이미 등록된 '
                '장소는 이 개수에 포함되지 않으며, 부족한 만큼 계속 다음 페이지를 조회합니다.'
            )
        )
        parser.add_argument(
            '--places', nargs='+', type=str, default=None,
            help=f'대상 동네를 직접 지정 (기본: 전체 - {", ".join(PLACES)})'
        )
        parser.add_argument(
            '--keywords', nargs='+', type=str, default=None,
            help=f'대상 키워드를 직접 지정 (기본: 전체 - {", ".join(flat_keywords())})'
        )
        parser.add_argument(
            '--interval', type=float, default=0.2,
            help='Naver API 과다 호출(429)을 피하기 위한 요청 간 최소 대기 시간(초). 기본 0.2초.'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='실제로 API를 호출하지 않고, 생성될 검색어 조합 목록만 출력합니다.'
        )

    def handle(self, *args, **options):
        combos = build_combinations(places=options['places'], keywords=options['keywords'])
        if not combos:
            raise CommandError('조합 결과가 비어 있습니다. --places / --keywords 값을 확인해주세요.')
        if options['per_combo'] <= 0:
            raise CommandError('--per-combo 는 1 이상이어야 합니다.')

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE(f"[auto_collect] (dry-run) 생성될 검색어 {len(combos)}개:"))
            for combo in combos:
                self.stdout.write(f"  - {combo}")
            self.stdout.write(self.style.NOTICE(
                "(dry-run이라 실제 API 호출/DB 저장은 하지 않았습니다. --dry-run 없이 다시 실행하세요.)"
            ))
            return

        self.stdout.write(self.style.NOTICE(
            f"[auto_collect] {len(combos)}개 조합 수집을 시작합니다 "
            f"(조합당 목표 신규 {options['per_combo']}건): {combos}"
        ))
        new_places, summary = auto_collect_from_targets(
            combos, per_combo=options['per_combo'], request_interval=options['interval']
        )

        for row in summary:
            self.stdout.write(
                f"  - {row['query']}: {row['created']}/{row['target']}건 등록 "
                f"(원본 {row['raw_fetched']}건 조회, {row['stopped_reason']})"
            )
        self.stdout.write(self.style.SUCCESS(
            f"[auto_collect] 완료. 신규 장소 {len(new_places)}건 등록. "
            f"리뷰까지 채우려면 `python manage.py refresh_naver --only-new` 를 실행하세요."
        ))
