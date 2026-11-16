import time

from django.core.management.base import BaseCommand, CommandError

from api.kakao_images import dong_names
from api.models import Place
from api.naver_miner import _store_structural_keywords


class Command(BaseCommand):
    help = "장소 좌표로 동 이름(법정동·행정동)을 받아 위치 키워드에 넣습니다. \"~동\"으로 검색할 수 있게 됩니다."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=0.1, help="요청 간 대기 시간(초)")

    def handle(self, *args, **options):
        first = Place.objects.filter(latitude__isnull=False).first()
        if first and dong_names(first.latitude, first.longitude) is None:
            raise CommandError("카카오 좌표→동 변환이 실패했습니다. KAKAO_REST_API_KEY와 카카오맵 활성화 설정을 확인하세요.")

        done = 0
        for place in Place.objects.order_by("id"):
            _store_structural_keywords(place)
            dongs = place.keywords.filter(keyword_type="location").values_list("keyword", flat=True)
            self.stdout.write(f"[{place.id}] {place.name}: {', '.join(dongs)}")
            done += 1
            time.sleep(options["interval"])
        self.stdout.write(self.style.SUCCESS(f"완료: {done}곳"))
