from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken 

from .models import PlaceAnalysis, Place, Review, Inquiry
from .serializers import (
    UserSerializer, SignupSerializer, PlaceSerializer, 
    ReviewSerializer, InquirySerializer
)
# [수정 사항 1] 서비스 파일명을 범수님이 사용 중인 gemini_service로 정확히 변경했습니다.
from .gemini_service import analyze_review, generate_response
from django.conf import settings

User = get_user_model()

# --- User Views ---

class CheckIDView(APIView):
    def get(self, request):
        username = request.query_params.get('id')
        if not username:
             return Response({'message': '아이디를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(username=username).exists():
            return Response({'isAvailable': False, 'message': '이미 사용 중인 아이디입니다.'}, status=200)
        return Response({'isAvailable': True, 'message': '사용 가능한 아이디입니다.'}, status=200)

class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('id')
        password = request.data.get('password')
        
        user = authenticate(username=username, password=password)
        if user:
            token = "sample_token_12345" 
            return Response({
                'token': token,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response({'message': '아이디 또는 비밀번호가 일치하지 않습니다.'}, status=status.HTTP_401_UNAUTHORIZED)

# --- Inquiry Views ---

class CreateInquiryView(generics.CreateAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class MyInquiriesView(generics.ListAPIView):
    serializer_class = InquirySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Inquiry.objects.filter(user=self.request.user)

class InquiryDetailView(generics.RetrieveAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    permission_classes = [permissions.IsAuthenticated]

# --- Place & Review Views ---

class PlaceDetailView(generics.RetrieveAPIView):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = [permissions.AllowAny]

class PlaceReviewsView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        place_id = self.kwargs['place_id']
        return Review.objects.filter(place_id=place_id)

class CreateReviewView(generics.CreateAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        place_id = self.request.data.get('place_id')
        place = get_object_or_404(Place, id=place_id)
        serializer.save(user=self.request.user, place=place)

class MyReviewsView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

# --- Search View ---

class SearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        keyword = request.query_params.get('keyword', '')
        if not keyword:
            return Response([], status=status.HTTP_200_OK)
            
        places = Place.objects.filter(name__icontains=keyword) | Place.objects.filter(address__icontains=keyword)
        
        results = []
        for place in places:
            from .models import PlaceImage, PlaceAnalysis
            images = PlaceImage.objects.filter(place=place).values_list('image_url', flat=True)
            latest_review = Review.objects.filter(place=place).first()
            
            non_ad_percent = 100
            ai_reason = "등록된 리뷰가 없어 검증을 생략합니다."
            
            if latest_review and latest_review.content:
                existing_analysis = PlaceAnalysis.objects.filter(name=place.name).first()
                
                if existing_analysis:
                    non_ad_percent = 100 - existing_analysis.ad_probability
                    ai_reason = existing_analysis.ai_summary + " (DB에 저장된 결과 재사용)"
                else:
                    ai_result = analyze_review(latest_review.content)
                    non_ad_percent = ai_result.get("non_ad_probability", 50)
                    ai_reason = ai_result.get("reason", "AI 신규 검증 완료")
                    
                    PlaceAnalysis.objects.create(
                        name=place.name,
                        content_text=latest_review.content,
                        is_ad=ai_result.get('is_ad', False),
                        ad_probability=100 - non_ad_percent,
                        ai_summary=ai_reason
                    )
            
            results.append({
                'id': place.id,
                'name': place.name,
                'address': place.address,
                'description': place.description,
                'images': list(images),
                'non_ad_probability': non_ad_percent,
                'ai_filtering_reason': ai_reason,
                'created_at': place.created_at.strftime('%Y-%m-%d')
            })
            
        return Response(results, status=status.HTTP_200_OK)
    
# --- Legacy/Analysis View (Keeping for backward compatibility or admin use) ---

class AnalyzePlaceView(APIView):
    def post(self, request):
        name = request.data.get('name')
        content = request.data.get('content')
        
        if not content:
            return Response({'error': '내용을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        ai_result = analyze_review(content)
        
        place = PlaceAnalysis.objects.create(
            name=name,
            content_text=content,
            is_ad=ai_result.get('is_ad', False),
            ad_probability=ai_result.get('probability', 100 - ai_result.get('non_ad_probability', 0)),
            ai_summary=ai_result.get('reason', '')
        )
        
        place.save() 
        
        return Response({
            'id': place.id,
            'name': place.name,
            'is_ad': place.is_ad,
            'probability': place.ad_probability,
            'reason': place.ai_summary,
            'model_used': getattr(settings, 'GEMINI_MODEL_NAME', 'unknown')
        }, status=status.HTTP_201_CREATED)

class AISearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        query = request.data.get('query')
        if not query:
            return Response({'message': '질문 내용을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        answer = generate_response(query)
        return Response({'answer': answer}, status=status.HTTP_200_OK)