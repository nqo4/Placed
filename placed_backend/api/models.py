from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model

# 1. 사용자 모델
class User(AbstractUser):
    # username(아이디), password, email은 기본 포함
    phone_number = models.CharField(max_length=20, blank=True, null=True)

# 2. 장소 분석 결과 모델 (데이터 출력용)
class PlaceAnalysis(models.Model):
    name = models.CharField(max_length=100)       # 장소 이름
    content_text = models.TextField()             # 분석한 리뷰 내용
    
    # AI 분석 결과
    is_ad = models.BooleanField(default=False)      # 광고 여부
    ad_probability = models.IntegerField(verbose_name='non ad probability', default=50) # 광고가 아닐 확률
    ai_summary = models.TextField(blank=True)       # AI 분석 이유
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.ad_probability}%)"

# 3. 장소 모델 (기본 정보)
class Place(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image_url = models.TextField(blank=True, null=True, help_text="장소 대표 이미지의 URL 주소.")
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return self.name

#3-1. 장소 사진 모델
class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

# 4. 리뷰 모델
class Review(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE) # 이제 정상 작동합니다.
    content = models.TextField()
    hashtags = models.CharField(max_length=255, blank=True, null=True)
    rating = models.IntegerField(default=5)
    url = models.URLField(unique=True, max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.place.name} - {self.user.username}"

# 5. 1:1 문의 모델
class Inquiry(models.Model):
    CATEGORY_CHOICES = [
        ('account', '계정 문의'),
        ('service', '서비스 이용'),
        ('etc', '기타'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inquiries')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='etc')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.category}] {self.user.username} - {self.message[:20]}"