from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Place, PlaceImage, Review, Inquiry, PlaceAnalysis

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number']

class SignupSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, write_only=True)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'phone_number']

    def create(self, validated_data):
        user_id = validated_data.get('id')
        if not user_id:
            user_id = validated_data.get('username')
            
        if not user_id:
            user_id = validated_data.get('email', '').split('@')[0]

        user_email = validated_data.get('email')
        if not user_email and '@' in str(user_id):
            user_email = user_id

        user = User.objects.create_user(
            username=user_id,
            email=user_email,
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number', '')
        )
        return user

class InquirySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Inquiry
        fields = ['id', 'user', 'category', 'message', 'created_at']

class PlaceSerializer(serializers.ModelSerializer):
    images = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='image_url'
    )
    
    class Meta:
        model = Place
        fields =['id',
                 'name',
                 'description',
                 'image_url', 
                 'address', 
                 'created_at', 
                 'images']

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    place_name = serializers.ReadOnlyField(source='place.name')

    class Meta:
        model = Review
        fields = ['id', 'place', 'place_name', 'user', 'content', 'rating', 'created_at']