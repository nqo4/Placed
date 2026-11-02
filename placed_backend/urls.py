from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')), # api 앱의 url 연결
]

# [추가] ECR-002/SFR-004: 개발 환경에서 업로드된(압축된) 이미지를 서빙하기 위한 설정.
# 운영 환경에서는 S3 등 별도 오브젝트 스토리지/CDN 사용을 권장합니다 (PER-002 최적화 참고).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)