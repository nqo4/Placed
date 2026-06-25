from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from .documents import PlaceDocument
from django.apps import apps
import json

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data

        analysis = PlaceAnalysis.objects.filter(name=instance.name).first()
        if analysis:
            data['non_ad_probability'] = analysis.ad_probability
            data['ai_filtering_reason'] = analysis.ai_summary
        else:
            data['non_ad_probability'] = None
            data['ai_filtering_reason'] = None

        return Response(data)

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
    

class ElasticSearchPlaceView(APIView):
    def get(self, request):
        query_string = request.query_params.get('search', '').strip()

        if not query_string:
            return Response({"error": "검색어를 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            search_results = PlaceDocument.search().query(
                "multi_match",
                query=query_string,
                fields=['name', 'description', 'address']
            )

            hits = search_results[:100].execute()

            response_data = []
            for hit in hits:
                place_id = int(hit.meta.id) if hasattr(hit, 'meta') else hit.id
                db_place = Place.objects.filter(id=place_id).first()
                
                real_image_url = ""
                
                if db_place:
                    image_manager = None
                    if hasattr(db_place, 'images'):
                        image_manager = db_place.images
                    elif hasattr(db_place, 'placeimage_set'):
                        image_manager = db_place.placeimage_set
                    elif hasattr(db_place, 'place_images'):
                        image_manager = db_place.place_images

                    if image_manager:
                        first_image_obj = image_manager.all().first()
                        if first_image_obj:
                            for attr in ['url', 'image', 'image_url', 'file']:
                                if hasattr(first_image_obj, attr):
                                    val = getattr(first_image_obj, attr)
                                    if val:
                                        real_image_url = val.url if hasattr(val, 'url') else str(val)
                                        break
                    
                    if not real_image_url and getattr(db_place, 'image_url', ''):
                        raw_images = db_place.image_url.strip()
                        if raw_images.startswith('[') and raw_images.endswith(']'):
                            try:
                                img_list = json.loads(raw_images)
                                if img_list: real_image_url = img_list[0]
                            except: pass
                        elif '\n' in raw_images or ',' in raw_images:
                            dlm = '\n' if '\n' in raw_images else ','
                            img_list = [i.strip() for i in raw_images.split(dlm) if i.strip()]
                            if img_list: real_image_url = img_list[0]
                        else:
                            real_image_url = raw_images

                if not real_image_url:
                    real_image_url = "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?q=80&w=500"

                response_data.append({
                    "id": place_id,
                    "name": hit.name,
                    "address": hit.address,
                    "description": hit.description,
                    "created_at": getattr(hit, 'created_at', ''),
                    "image_url": real_image_url,
                })

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Search server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)