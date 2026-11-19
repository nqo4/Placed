from django.core.management.base import BaseCommand

from api.models import Place
from api.naver_miner import store_menu_keywords


class Command(BaseCommand):
    help = "광고가 아닌 후기에 나온 음식 이름(짬뽕, 케이크 등)을 장소의 메뉴 키워드로 저장합니다. AI·외부 API를 쓰지 않습니다."

    def handle(self, *args, **options):
        found = 0
        for place in Place.objects.order_by("id"):
            menus = store_menu_keywords(place)
            found += bool(menus)
            self.stdout.write(f"[{place.id}] {place.name}: {', '.join(menus) or '-'}")
        self.stdout.write(self.style.SUCCESS(f"완료: 메뉴 키워드가 있는 장소 {found}곳"))
