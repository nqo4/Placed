import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from api.models import Place
from api.naver_miner import ImageSearchError, _get_naver_headers, find_place_images, save_place_images


class Command(BaseCommand):
    help = (
        "기존 장소의 외부 사진을 다시 받습니다. 사진이 실린 글 제목에 상호명이 있는 사진만 남기고, "
        "맞는 사진이 없으면 비워 둡니다. 사용자가 직접 올린 사진은 그대로 둡니다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력")
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 장소 수")
        parser.add_argument("--start-id", type=int, default=None, help="이 id부터 처리 (중단된 곳부터 이어서)")
        parser.add_argument("--interval", type=float, default=0.2, help="요청 간 대기 시간(초)")

    def handle(self, *args, **options):
        headers = _get_naver_headers()
        if not headers:
            raise CommandError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET이 설정되지 않았습니다.")

        places = Place.objects.order_by("id")
        if options["start_id"]:
            places = places.filter(id__gte=options["start_id"])
        if options["limit"]:
            places = places[: options["limit"]]

        dry = options["dry_run"]
        found = empty = 0
        for place in places:
            try:
                links = find_place_images(
                    place.name, place.address, headers, interval=options["interval"], strict=True
                )
            except ImageSearchError:
                # 요청 실패를 "사진 없음"으로 보고 기존 사진을 지우면 안 되므로 여기서 멈춥니다.
                raise CommandError(f"이미지 검색 실패로 중단했습니다. --start-id {place.id} 로 이어서 실행하세요.")

            old = place.images.filter(Q(image="") | Q(image__isnull=True))
            if not dry:
                with transaction.atomic():
                    old.delete()
                    saved = save_place_images(place, links)
            else:
                saved = len(links)
            found += bool(saved)
            empty += not saved
            self.stdout.write(f"[{place.id}] {place.name}: 사진 {saved}장")
            time.sleep(options["interval"])

        verb = "확인" if dry else "갱신"
        self.stdout.write(self.style.SUCCESS(f"{verb} 완료: 사진 있음 {found}곳, 사진 없음 {empty}곳"))
