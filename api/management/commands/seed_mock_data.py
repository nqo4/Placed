from django.core.management.base import BaseCommand

from api.data_dump import insert_mock_data


class Command(BaseCommand):
    """
    [추가 개발] api/data_dump.py의 insert_mock_data()도 mine_naver와 마찬가지로
    호출부가 없어 실행할 방법이 없었습니다. 로컬 개발/데모용 목업 데이터 적재를
    관리 명령으로 노출합니다. (최소 1명의 User가 미리 존재해야 합니다 - createsuperuser 등)

    사용법:
        python manage.py seed_mock_data
    """

    help = "대전 지역 목업(더미) 장소/리뷰 데이터를 DB에 적재합니다."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('[seed_mock_data] 목업 데이터 적재를 시작합니다...'))
        insert_mock_data()
        self.stdout.write(self.style.SUCCESS('[seed_mock_data] 완료.'))
