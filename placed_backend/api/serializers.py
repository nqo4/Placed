from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Place, Review, Inquiry, PlaceAnalysis

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number']

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'phone_number']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
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
    class Meta:
        model = Place
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    place_name = serializers.ReadOnlyField(source='place.name')

    class Meta:
        model = Review
        fields = ['id', 'place', 'place_name', 'user', 'content', 'rating', 'created_at']
