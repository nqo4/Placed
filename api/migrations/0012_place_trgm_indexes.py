# [자연어 검색 보강] Place.name / Place.address에 trigram GIN 인덱스를 추가합니다.
# TrigramSimilarity 자체는 인덱스가 없어도 동작하지만, 장소 수가 늘어나면 매번 전체
# 테이블을 스캔하게 되므로 검색 성능을 위해 인덱스를 둡니다. 0011에서 pg_trgm 확장을
# 먼저 설치해야 gin_trgm_ops opclass를 쓸 수 있습니다.
import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_pg_trgm_extension'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='place',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['name'], name='place_name_trgm_idx', opclasses=['gin_trgm_ops']
            ),
        ),
        migrations.AddIndex(
            model_name='place',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['address'], name='place_address_trgm_idx', opclasses=['gin_trgm_ops']
            ),
        ),
    ]
