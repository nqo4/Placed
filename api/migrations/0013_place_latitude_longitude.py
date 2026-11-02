# [거리 기반 추천] Place에 좌표(latitude/longitude) 필드를 추가합니다. 이 마이그레이션
# 이전에 등록된 장소는 값이 비어 있으며(null), 재수집 전까지는 거리 기반 추천에서
# 제외되고 키워드 유사도만으로 평가됩니다(api/recommendation.py의 similar_places_for).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_place_trgm_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='place',
            name='latitude',
            field=models.FloatField(blank=True, help_text='WGS84 위도', null=True),
        ),
        migrations.AddField(
            model_name='place',
            name='longitude',
            field=models.FloatField(blank=True, help_text='WGS84 경도', null=True),
        ),
    ]
