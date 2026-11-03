from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Place, PlaceImage, Review, Inquiry, PlaceAnalysis

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'email', 'phone_number']

class SignupSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, write_only=True)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'email', 'phone_number']

    def create(self, validated_data):
        user_id = validated_data.get('id')
        if not user_id:
            user_id = validated_data.get('username')

        if not user_id:
            # [버그 수정] email이 아예 안 넘어오면 .get('email', '')이 기본값 ''을 주지만,
            # allow_null=True라서 email=None이 명시적으로 넘어오면 .get()이 None을 그대로
            # 반환해 .split('@')에서 AttributeError가 발생했습니다.
            user_id = (validated_data.get('email') or '').split('@')[0]

        user_email = validated_data.get('email')
        if not user_email and '@' in str(user_id):
            user_email = user_id

        user = User.objects.create_user(
            username=user_id,
            email=user_email,
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            phone_number=validated_data.get('phone_number', '')
        )
        return user

class InquirySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Inquiry
        fields = ['id', 'user', 'category', 'message', 'answer', 'created_at']
        # 답변은 관리자 답변 API(InquiryAnswerSerializer)로만 저장합니다.
        read_only_fields = ['answer']


class InquiryAnswerSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(allow_blank=False)

    class Meta:
        model = Inquiry
        fields = ['answer']

class PlaceImageSerializer(serializers.ModelSerializer):
    # [수정] 기존에는 SlugRelatedField(slug_field='image_url')로 크롤링된 외부 URL만
    # 노출했습니다. 직접 업로드해 압축 저장한 이미지(image 필드)는 표현할 방법이 없었으므로
    # 두 출처를 하나의 url로 합쳐서 내려줍니다.
    url = serializers.SerializerMethodField()

    class Meta:
        model = PlaceImage
        fields = ['id', 'url', 'created_at']

    def get_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return obj.image_url


class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, read_only=True)
    # [추가] 키워드 기반 장소 구분 - 위치/종류/분위기 키워드를 종류별로 묶어서 내려줍니다.
    # (해시태그 대신 쓰는 통제된 키워드. api/keyword_taxonomy.py, api/recommendation.py 참고)
    keywords = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields =['id',
                 'name',
                 'description',
                 'category',
                 'image_url',
                 'address',
                 'latitude',
                 'longitude',
                 'created_at',
                 'images',
                 'keywords']

    def get_keywords(self, obj):
        grouped = {'location': [], 'category': [], 'mood': []}
        for kw in obj.keywords.all():
            grouped.setdefault(kw.keyword_type, []).append(kw.keyword)
        return grouped


class PlaceImageUploadSerializer(serializers.ModelSerializer):
    """[추가] ECR-002/SFR-004: 업로드된 이미지를 압축해 저장하기 위한 시리얼라이저."""
    class Meta:
        model = PlaceImage
        fields = ['id', 'place', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    place_name = serializers.ReadOnlyField(source='place.name')

    class Meta:
        model = Review
        fields = ['id', 'place', 'place_name', 'user', 'content', 'rating', 'created_at']


# 관리자용 - is_staff, date_joined 포함
class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'email', 'phone_number', 'is_staff', 'date_joined']


class PlaceAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceAnalysis
        fields = ['id', 'name', 'is_ad', 'ad_probability', 'ai_summary', 'created_at']