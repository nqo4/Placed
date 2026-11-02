from django.db import migrations, models


def mark_default_scores_as_failed(apps, schema_editor):
    # 기존 데이터에는 실패 기록이 없어 오류 기본값과 같은 50%를 모두 재분석 대상으로 표시합니다.
    # 실제 판정이 50%였던 글도 포함되지만, 한 번 더 분석될 뿐 결과가 틀어지지는 않습니다.
    ReviewSource = apps.get_model('api', 'ReviewSource')
    ReviewSource.objects.filter(ad_probability=50).update(analysis_failed=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_reviewsource_is_review_exclude_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewsource',
            name='analysis_failed',
            field=models.BooleanField(default=False, help_text='AI 분석 실패로 기본값이 저장된 글인지'),
        ),
        migrations.RunPython(mark_default_scores_as_failed, migrations.RunPython.noop),
    ]
