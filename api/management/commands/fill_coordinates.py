import json
import time

from django.core.management.base import BaseCommand, CommandError

from api.models import Place
from api.naver_miner import (
    _extract_coordinates,
    _extract_name_address,
    _get_naver_headers,
    _request_with_retry,
    _search_url,
)
from api.recommendation import region_hint


def _normalize(text):
    return "".join((text or "").split())


def _address_close(a, b):
    # "...6" 과 "...6 2층" 처럼 한쪽이 다른 쪽으로 시작하면 같은 주소로 봄
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def _pick_item(place, items):
    name, address = _normalize(place.name), _normalize(place.address)
    region = _normalize(region_hint(place.address))

    exact, close, address_only, same_region = None, None, None, []
    for item in items:
        item_name, item_address = _extract_name_address(item)
        addrs = [_normalize(item_address), _normalize(item.get("address"))]
        same_name = _normalize(item_name) == name

        if address in addrs:
            if same_name:
                exact = exact or item
            else:
                address_only = address_only or item
        elif same_name and any(_address_close(address, a) for a in addrs):
            close = close or item
        elif same_name and region and addrs[0].startswith(region):
            same_region.append(item)

    # 이사한 경우: 같은 구에 같은 이름이 딱 1곳일 때만
    moved = same_region[0] if len(same_region) == 1 else None
    return exact or close or address_only or moved


class Command(BaseCommand):
    help = "좌표가 비어 있는 장소에 네이버 지역검색으로 위도/경도를 채웁니다."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력")
        parser.add_argument("--limit", type=int, default=None, help="처리할 최대 장소 수")
        parser.add_argument("--interval", type=float, default=0.2, help="요청 간 대기 시간(초)")

    def handle(self, *args, **options):
        headers = _get_naver_headers()
        if headers is None:
            raise CommandError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 설정이 없습니다.")

        places = Place.objects.filter(latitude__isnull=True).order_by("id")
        if options["limit"]:
            places = places[: options["limit"]]

        dry_run = options["dry_run"]
        filled, failed = 0, []

        for place in places:
            query = f"{region_hint(place.address)} {place.name}".strip()
            response = _request_with_retry(_search_url("local", query, display=5), headers)
            time.sleep(options["interval"])

            items = []
            if response is not None:
                try:
                    items = response.json().get("items", [])
                except json.JSONDecodeError:
                    items = []

            item = _pick_item(place, items)
            lat, lng = _extract_coordinates(item) if item else (None, None)
            if lat is None:
                failed.append(place)
                self.stdout.write(f"  실패  {place.id} {place.name} ({place.address})")
                continue

            filled += 1
            self.stdout.write(f"  성공  {place.id} {place.name} -> {lat:.6f}, {lng:.6f}")
            if not dry_run:
                place.latitude, place.longitude = lat, lng
                place.save(update_fields=["latitude", "longitude"])

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}성공 {filled}개 / 실패 {len(failed)}개"))
