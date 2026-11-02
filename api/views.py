from rest_framework import generics, status, permissions, parsers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PlaceAnalysis, Place, PlaceImage, Review, Inquiry, SearchLog, PlaceViewLog
from .serializers import (
    UserSerializer, SignupSerializer, PlaceSerializer,
    ReviewSerializer, InquirySerializer, PlaceImageUploadSerializer,
    PlaceImageSerializer, AdminUserSerializer, PlaceAnalysisSerializer
)
# [수정 사항 1] 서비스 파일명을 범수님이 사용 중인 gemini_service로 정확히 변경했습니다.
from .gemini_service import analyze_review, generate_response
from .image_utils import compress_image
# [추가] SFR-005/SFR-007/DAR-002 고도화: 검색 키워드 + 선택한 장소 기반 추천 스코어링 로직
from .recommendation import (
    recommend_places_for_user, daily_recommended_places, find_matching_places, similar_places_for
)
from .keyword_taxonomy import PLACE_TYPE_LABELS
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
            # [버그 수정] 기존에는 고정 문자열 "sample_token_12345"를 모든 로그인에 대해
            # 동일하게 발급하고 있었습니다 — 사실상 인증이 없는 것과 같아 SER-001(보안
            # 요구사항)을 충족하지 못했습니다. rest_framework_simplejwt로 실제 access/refresh
            # 토큰을 발급하도록 수정했습니다. (settings.REST_FRAMEWORK가 JWTAuthentication을
            # 기본 인증 클래스로 사용하도록 이미 구성되어 있습니다.)
            refresh = RefreshToken.for_user(user)
            access = str(refresh.access_token)
            return Response({
                'access': access,
                'refresh': str(refresh),
                # 프론트엔드 Login.js가 읽는 키 (access와 같은 값)
                'token': access,
                'is_staff': user.is_staff,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response({'message': '아이디 또는 비밀번호가 일치하지 않습니다.'}, status=status.HTTP_401_UNAUTHORIZED)


# [추가] SFR-001 계정 관리 요구사항: 아이디 찾기
# 원문 요구사항은 "이메일, 전화번호 인증에 성공하면"이라고 되어 있으나, 실제 SMS/이메일
# 인증번호 발송은 외부 서비스(예: 알리고, AWS SES 등) 연동이 필요해 이번 저장소 범위를
# 벗어납니다. 여기서는 이메일+전화번호가 모두 일치하는지 확인하는 검증 단계까지 구현했고,
# 인증번호 발송/검증 단계는 추후 외부 서비스 연동 지점으로 명시해 두었습니다.
class FindIdView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        phone_number = request.data.get('phone_number')

        if not email or not phone_number:
            return Response({'message': '이메일과 전화번호를 모두 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email, phone_number=phone_number).first()
        if not user:
            return Response({'message': '일치하는 계정을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        username = user.username
        if len(username) <= 2:
            masked = username[0] + '*' * (len(username) - 1)
        else:
            masked = username[0] + '*' * (len(username) - 2) + username[-1]

        return Response({'username': masked}, status=status.HTTP_200_OK)


# [추가] SFR-001 계정 관리 요구사항: 비밀번호 재설정
class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('id')
        email = request.data.get('email')
        phone_number = request.data.get('phone_number')
        new_password = request.data.get('new_password')

        if not all([username, email, phone_number, new_password]):
            return Response(
                {'message': '아이디, 이메일, 전화번호, 새 비밀번호를 모두 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(username=username, email=email, phone_number=phone_number).first()
        if not user:
            return Response({'message': '일치하는 계정을 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        if len(new_password) < 8:
            return Response({'message': '비밀번호는 8자 이상이어야 합니다.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'message': '비밀번호가 변경되었습니다.'}, status=status.HTTP_200_OK)


# [추가] SFR-001 계정 관리 요구사항: 회원 탈퇴
# "계정 탈퇴 버튼을 누르면 재확인용 컨펌창을 띄우고..." - 재확인 UI 자체는 프론트엔드 몫이지만,
# 백엔드는 실수로 탈퇴되는 것을 막기 위해 현재 비밀번호 재확인을 요구합니다.
class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        password = request.data.get('password')
        if not password or not request.user.check_password(password):
            return Response({'message': '비밀번호가 일치하지 않습니다.'}, status=status.HTTP_401_UNAUTHORIZED)

        request.user.delete()
        return Response({'message': '회원 탈퇴가 완료되었습니다.'}, status=status.HTTP_200_OK)

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
        response = super().retrieve(request, *args, **kwargs)
        # [추가] SFR-005/SFR-007/DAR-002: 로그인 사용자가 실제로 장소 상세를 조회(=선택)한
        # 이력을 추천 시스템의 행동 데이터로 남깁니다(api/recommendation.py 참고). 비로그인
        # 사용자는 SearchLog와 동일하게 기록하지 않습니다. get_object()가 404를 던지면 위
        # super().retrieve() 호출에서 예외가 발생해 아래 코드는 실행되지 않습니다.
        if request.user and request.user.is_authenticated:
            PlaceViewLog.objects.create(user=request.user, place_id=self.kwargs['pk'])

        # 프론트엔드 PlaceDetail.js가 표시하는 AI 분석 결과. 분석 전이면 None입니다.
        analysis = PlaceAnalysis.objects.filter(name=response.data['name']).first()
        response.data['non_ad_probability'] = 100 - analysis.ad_probability if analysis else None
        response.data['ai_filtering_reason'] = analysis.ai_summary if analysis else None
        return response


# [추가] 장소 상세 - "이런 곳은 어때요" 비슷하거나 가까운 매장 추천. PlaceDetailView에서
# 장소 상세를 열어볼 때 함께 호출하는 용도입니다. 로그인 여부와 무관하게(AllowAny) 동작
# 합니다 - 개인 행동 기록이 아니라 장소 대 장소 유사도/거리만 보는 추천이라, 검색/비로그인
# 사용자에게도 똑같이 의미가 있습니다. 실제 계산은 api/recommendation.py의
# similar_places_for() 참고.
class SimilarPlacesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        place = get_object_or_404(Place, pk=pk)
        similar = similar_places_for(place)

        results = []
        for row in similar:
            data = PlaceSerializer(row['place'], context={'request': request}).data
            data['distance_km'] = round(row['distance_km'], 2) if row['distance_km'] is not None else None
            results.append(data)

        return Response({'results': results}, status=status.HTTP_200_OK)


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

    def _search_places(self, keyword):
        """
        [키워드 인식 검색] 실제 매칭 로직은 api/recommendation.py의 find_matching_places()
        참고 - export_recommendation_dataset.py(추천용 데이터셋 구축)가 "이 검색으로 어떤
        장소들이 노출됐는지"를 재구성할 때도 동일한 함수를 재사용하므로, 두 곳의 매칭
        기준이 어긋나지 않도록 로직을 한 곳에 모아뒀습니다.
        """
        return find_matching_places(keyword)

    def get(self, request):
        keyword = request.query_params.get('keyword', '').strip()
        if not keyword:
            return Response({'results': [], 'excluded_ad_count': 0}, status=status.HTTP_200_OK)

        places = self._search_places(keyword)

        # [추가] SFR-005/DAR-002: 로그인한 사용자의 검색 기록을 저장해 개인화 추천(RecommendView)의
        # 기반 데이터로 사용합니다. 비로그인 사용자의 검색은 기록하지 않습니다.
        if request.user and request.user.is_authenticated:
            SearchLog.objects.create(user=request.user, keyword=keyword)

        ad_threshold = getattr(settings, 'AD_EXCLUDE_THRESHOLD', 70)

        results = []
        excluded_ad_count = 0
        for place in places:
            images = PlaceImage.objects.filter(place=place)
            latest_review = Review.objects.filter(place=place).first()

            non_ad_percent = 100
            ai_reason = "등록된 리뷰가 없어 검증을 생략합니다."
            ad_probability = 0

            if latest_review and latest_review.content:
                existing_analysis = PlaceAnalysis.objects.filter(name=place.name).first()

                if existing_analysis:
                    ad_probability = existing_analysis.ad_probability
                    non_ad_percent = 100 - ad_probability
                    ai_reason = existing_analysis.ai_summary + " (DB에 저장된 결과 재사용)"
                else:
                    ai_result = analyze_review(latest_review.content)
                    non_ad_percent = ai_result.get("non_ad_probability", 50)
                    ad_probability = 100 - non_ad_percent
                    ai_reason = ai_result.get("reason", "AI 신규 검증 완료")

                    PlaceAnalysis.objects.create(
                        name=place.name,
                        content_text=latest_review.content,
                        is_ad=ai_result.get('is_ad', False),
                        ad_probability=ad_probability,
                        ai_summary=ai_reason
                    )

            # [추가] SFR-002/SFR-004/SFR-008: 기존에는 광고 확률을 계산만 하고 실제로는
            # 결과에서 제외하지 않았습니다. 요구사항대로 임계치 이상이면 결과에서 제외하고,
            # 총 제외 개수를 함께 응답합니다.
            if ad_probability >= ad_threshold:
                excluded_ad_count += 1
                continue

            results.append({
                'id': place.id,
                'name': place.name,
                'address': place.address,
                'description': place.description,
                'images': PlaceImageSerializer(images, many=True, context={'request': request}).data,
                'non_ad_probability': non_ad_percent,
                'ai_filtering_reason': ai_reason,
                'created_at': place.created_at.strftime('%Y-%m-%d')
            })

        return Response({
            'results': results,
            'excluded_ad_count': excluded_ad_count,
        }, status=status.HTTP_200_OK)


# [고도화] SFR-005/SFR-007/DAR-002: 로그인 사용자 행동 패턴 기반 추천
# 원 요구사항(SFR-007)이 명시한 Neural CF 모델은 별도의 학습 파이프라인/데이터셋이 필요해
# 이번 저장소 범위를 벗어납니다(향후 과제로 report에 별도 명시). 대신 지금 쌓이는 행동
# 데이터(검색 키워드 SearchLog + 실제로 선택/조회한 장소 PlaceViewLog)로 동작하는
# 컨텐츠 기반 베이스라인으로, 해시태그·업종(카테고리)·지역이 겹치는 장소를 우선순위로
# 추천합니다. 실제 스코어링 로직은 api/recommendation.py 참고.
class RecommendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        results, has_history = recommend_places_for_user(request.user)

        if not has_history:
            return Response({
                'results': [],
                'message': '아직 검색/조회 기록이 없어 추천할 수 없습니다.'
            }, status=status.HTTP_200_OK)

        return Response({
            'results': [
                PlaceSerializer(place, context={'request': request}).data
                for place in results
            ]
        }, status=status.HTTP_200_OK)


# [추가] 오늘의 추천 장소 - 로그인 첫 화면에 식당/카페/술집 각 1곳씩 노출합니다.
# RecommendView(상위 10건, 검색+조회 통합)와 달리 오직 검색 기록만 보고, "1) 주로 검색한
# 동네 2) 주로 검색한 연관 키워드" 순서로 우선순위를 매깁니다. 실제 선정 로직은
# api/recommendation.py의 daily_recommended_places() 참고.
class DailyRecommendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        results, has_history = daily_recommended_places(request.user)

        serialized = {
            PLACE_TYPE_LABELS[place_type]: (
                PlaceSerializer(place, context={'request': request}).data if place else None
            )
            for place_type, place in results.items()
        }

        response_data = {'results': serialized}
        if not has_history:
            response_data['message'] = '아직 검색 기록이 없어 추천할 수 없습니다.'

        return Response(response_data, status=status.HTTP_200_OK)


# [추가] ECR-002/SFR-004: 이미지 업로드 + 압축 저장
class UploadPlaceImageView(generics.CreateAPIView):
    queryset = PlaceImage.objects.all()
    serializer_class = PlaceImageUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('image')
        if uploaded_file:
            compressed = compress_image(uploaded_file)
            serializer.save(image=compressed)
        else:
            serializer.save()
    
# --- Legacy/Analysis View (Keeping for backward compatibility or admin use) ---

class AnalyzePlaceView(APIView):
    # [추가] QUR-001 요금 과다 방지: 이 엔드포인트는 인증 없이 호출될 때마다 Gemini API를
    # 호출하며 DB에 기록을 남기므로, 익명 사용자의 과다 호출로 인한 비용 폭탄 위험이 있었습니다.
    throttle_scope = 'ai'

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
    # [추가] QUR-001 요금 과다 방지: 위와 동일한 이유로 호출 빈도를 제한합니다.
    throttle_scope = 'ai'

    def post(self, request):
        query = request.data.get('query')
        if not query:
            return Response({'message': '질문 내용을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        answer = generate_response(query)
        return Response({'answer': answer}, status=status.HTTP_200_OK)


# 프론트엔드 searchAPI.js가 호출하는 /api/search/elastic/ 경로를 유지합니다. Elasticsearch는
# pg_trgm으로 대체했으므로 실제 매칭은 find_matching_places()가 담당합니다. 목록 조회마다
# Gemini를 호출하지 않도록, 이미 저장된 분석 결과로만 광고 의심 장소를 제외합니다.
class PlaceKeywordSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        keyword = request.query_params.get('search', '').strip()
        if not keyword:
            return Response({'error': '검색어를 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        places = find_matching_places(keyword)
        ad_threshold = getattr(settings, 'AD_EXCLUDE_THRESHOLD', 70)
        ad_names = set(
            PlaceAnalysis.objects.filter(ad_probability__gte=ad_threshold).values_list('name', flat=True)
        )

        results = []
        for place in places:
            if place.name in ad_names:
                continue
            first_image = PlaceImage.objects.filter(place=place).first()
            image_url = (
                PlaceImageSerializer(first_image, context={'request': request}).data['url']
                if first_image else place.image_url
            )
            results.append({
                'id': place.id,
                'name': place.name,
                'address': place.address,
                'description': place.description,
                'created_at': place.created_at,
                'image_url': image_url or '',
            })
        return Response(results, status=status.HTTP_200_OK)


# --- Admin Views ---
# 회원 개인정보가 포함되므로 관리자(is_staff) 계정만 조회할 수 있습니다.

class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminPlaceListView(generics.ListAPIView):
    queryset = Place.objects.all().order_by('-created_at')
    serializer_class = PlaceSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminAnalysisListView(generics.ListAPIView):
    queryset = PlaceAnalysis.objects.all().order_by('-created_at')
    serializer_class = PlaceAnalysisSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminReviewListView(generics.ListAPIView):
    queryset = Review.objects.all().order_by('-created_at')
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminInquiryListView(generics.ListAPIView):
    queryset = Inquiry.objects.all().order_by('-created_at')
    serializer_class = InquirySerializer
    permission_classes = [permissions.IsAdminUser]