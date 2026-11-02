# [자연어 검색 보강 - Elasticsearch 대신 PostgreSQL 확장 사용]
# pg_trgm 확장을 PostgreSQL DB에 설치합니다(CREATE EXTENSION IF NOT EXISTS pg_trgm).
# 이후 마이그레이션(0012)에서 추가하는 trigram GIN 인덱스, 그리고
# api/recommendation.py의 find_matching_places()가 쓰는 TrigramSimilarity가
# 이 확장을 전제로 동작합니다. Render의 관리형 PostgreSQL도 pg_trgm을 지원합니다
# (render.com/docs/postgresql-extensions).
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_reviewsource_has_place_info'),
    ]

    operations = [
        TrigramExtension(),
    ]
