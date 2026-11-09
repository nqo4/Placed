"""
[추가 개발] TER-001/TER-002/TER-003 테스트 요구사항 대응.
기존 저장소에는 테스트 코드가 전혀 없었습니다. 회원가입/로그인 같은 핵심 웹 기능(TER-001)과
AI 광고 판별·필터링 결과(TER-003, SFR-004/008), 그리고 네이버 크롤러(DAR-001/DAR-004)의
자동화/오류 처리/증분 갱신 로직을 자동으로 검증합니다.

실행: python manage.py test api
"""
import io
import json
import os
import shutil
import tempfile
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from . import naver_miner, recommendation
from .gemini_service import analyze_review
from .keyword_taxonomy import MOOD_KEYWORDS, classify_place_type
from .models import Inquiry, Place, PlaceAnalysis, PlaceImage, PlaceKeyword, PlaceViewLog, Review, ReviewSource, SearchLog

User = get_user_model()


class AccountTests(APITestCase):
    """TER-001: 계정 관련 웹 기능이 정상 동작하는지 확인 (SFR-001)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tester01', password='StrongPass123',
            email='tester01@example.com', phone_number='01012345678'
        )

    def test_check_id_available(self):
        res = self.client.get(reverse('check-id'), {'id': 'brand_new_id'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['isAvailable'])

    def test_check_id_taken(self):
        res = self.client.get(reverse('check-id'), {'id': 'tester01'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['isAvailable'])

    def test_signup_creates_user(self):
        res = self.client.post(reverse('signup'), {
            'id': 'newbie', 'password': 'AnotherPass123',
            'email': 'newbie@example.com', 'phone_number': '01099998888'
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newbie').exists())

    def test_login_returns_real_jwt_tokens(self):
        """[버그 회귀 테스트] 고정 문자열 토큰이 아니라 진짜 JWT가 발급되어야 함."""
        res = self.client.post(reverse('login'), {'id': 'tester01', 'password': 'StrongPass123'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertNotEqual(res.data['access'], 'sample_token_12345')
        # access 토큰으로 인증이 필요한 엔드포인트를 호출할 수 있어야 함
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.client.get(reverse('my-reviews'))
        self.assertEqual(me.status_code, 200)

    def test_login_wrong_password_rejected(self):
        res = self.client.post(reverse('login'), {'id': 'tester01', 'password': 'wrong'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_find_id_masks_username(self):
        res = self.client.post(reverse('find-id'), {
            'email': 'tester01@example.com', 'phone_number': '01012345678'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['username'].startswith('t'))
        self.assertIn('*', res.data['username'])

    def test_find_id_no_match(self):
        res = self.client.post(reverse('find-id'), {
            'email': 'nobody@example.com', 'phone_number': '00000000000'
        })
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_password_reset_changes_password(self):
        res = self.client.post(reverse('password-reset'), {
            'id': 'tester01', 'email': 'tester01@example.com',
            'phone_number': '01012345678', 'new_password': 'BrandNewPass123'
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass123'))

    def test_delete_account_requires_correct_password(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(reverse('delete-account'), {'password': 'wrong'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(User.objects.filter(username='tester01').exists())

    def test_delete_account_success(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(reverse('delete-account'), {'password': 'StrongPass123'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username='tester01').exists())


class SearchAdFilterTests(APITestCase):
    """TER-003/SFR-004/SFR-008: AI 광고 판별 결과가 실제로 검색 결과에서 제외되는지 확인."""

    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='pw12345678')
        self.genuine_place = Place.objects.create(name='진짜맛집', address='대전 유성구')
        self.ad_place = Place.objects.create(name='진짜맛집 광고점', address='대전 유성구')

        Review.objects.create(place=self.genuine_place, user=self.user, content='내돈내산 후기입니다')
        Review.objects.create(place=self.ad_place, user=self.user, content='협찬받아 작성한 글입니다')

        # 이미 분석된 결과를 미리 저장해 Gemini 호출 없이 필터링 로직만 검증
        PlaceAnalysis.objects.create(
            name=self.genuine_place.name, content_text='내돈내산 후기입니다',
            is_ad=False, ad_probability=10, ai_summary='진짜 후기로 판단'
        )
        PlaceAnalysis.objects.create(
            name=self.ad_place.name, content_text='협찬받아 작성한 글입니다',
            is_ad=True, ad_probability=90, ai_summary='협찬 문구 발견'
        )

    def test_high_ad_probability_place_is_still_listed(self):
        # 광고성 글은 글 단위로 걸러내므로 장소 자체는 검색 결과에서 빼지 않습니다.
        res = self.client.get(reverse('search'), {'keyword': '진짜맛집'})
        self.assertEqual(res.status_code, 200)
        names = [r['name'] for r in res.data['results']]
        self.assertIn(self.genuine_place.name, names)
        self.assertIn(self.ad_place.name, names)
        self.assertEqual(res.data['excluded_ad_count'], 0)

    def test_authenticated_search_is_logged(self):
        self.client.force_authenticate(user=self.user)
        self.client.get(reverse('search'), {'keyword': '진짜맛집'})
        self.assertTrue(SearchLog.objects.filter(user=self.user, keyword='진짜맛집').exists())

    def test_anonymous_search_is_not_logged(self):
        self.client.get(reverse('search'), {'keyword': '진짜맛집'})
        self.assertEqual(SearchLog.objects.count(), 0)

    @patch('api.views.analyze_review')
    def test_new_place_calls_ai_and_persists_result(self, mock_analyze):
        mock_analyze.return_value = {
            'is_ad': False, 'non_ad_probability': 88, 'reason': '테스트용 응답'
        }
        fresh_place = Place.objects.create(name='신규장소', address='대전 서구')
        Review.objects.create(place=fresh_place, user=self.user, content='새로운 리뷰')

        res = self.client.get(reverse('search'), {'keyword': '신규장소'})
        self.assertEqual(res.status_code, 200)
        mock_analyze.assert_called_once()
        self.assertTrue(PlaceAnalysis.objects.filter(name='신규장소', ad_probability=12).exists())


class SearchKeywordAwareTests(APITestCase):
    """
    [키워드 인식 검색] 검색어가 장소명/주소에 그대로 "포함"될 때만 결과가 나오는 게 아니라,
    PlaceKeyword(위치/종류/분위기)를 인식해서 매칭되는지 확인. 리뷰가 없는 장소는 광고
    판별 없이 바로 노출되므로(SearchView.get 참고) 이 테스트들은 리뷰를 만들지 않는다.
    """

    def setUp(self):
        self.quiet_cafe = Place.objects.create(name='스타벅스 궁동점', address='대전 유성구 궁동')
        for keyword_type, keyword in [
            ('location', '대전 유성구'), ('category', '카페'), ('mood', '조용한'),
        ]:
            PlaceKeyword.objects.create(place=self.quiet_cafe, keyword_type=keyword_type, keyword=keyword)

        self.loud_cafe = Place.objects.create(name='이디야 궁동점', address='대전 유성구 궁동')
        for keyword_type, keyword in [('location', '대전 유성구'), ('category', '카페')]:
            PlaceKeyword.objects.create(place=self.loud_cafe, keyword_type=keyword_type, keyword=keyword)

        self.other_region_cafe = Place.objects.create(name='별다방', address='서울 강남구')
        for keyword_type, keyword in [('location', '서울 강남구'), ('category', '카페')]:
            PlaceKeyword.objects.create(place=self.other_region_cafe, keyword_type=keyword_type, keyword=keyword)

    def test_search_matches_keyword_not_in_name_or_address(self):
        """장소명/주소 어디에도 없는 단어("카페")라도 category 키워드로 매칭돼야 함."""
        res = self.client.get(reverse('search'), {'keyword': '카페'})
        names = [r['name'] for r in res.data['results']]
        self.assertIn(self.quiet_cafe.name, names)
        self.assertIn(self.loud_cafe.name, names)
        self.assertIn(self.other_region_cafe.name, names)

    def test_search_requires_all_tokens_to_match(self):
        """여러 단어로 검색하면 전부 만족하는 장소만 나와야 함(AND)."""
        res = self.client.get(reverse('search'), {'keyword': '유성구 조용한 카페'})
        names = [r['name'] for r in res.data['results']]
        self.assertIn(self.quiet_cafe.name, names)
        self.assertNotIn(self.loud_cafe.name, names)  # mood(조용한) 키워드가 없음
        self.assertNotIn(self.other_region_cafe.name, names)  # 지역이 다름

    def test_search_no_duplicate_results_when_multiple_keywords_match(self):
        """한 장소가 여러 키워드에 매칭돼도 결과에 중복으로 나오면 안 됨."""
        res = self.client.get(reverse('search'), {'keyword': '유성구 카페'})
        names = [r['name'] for r in res.data['results']]
        self.assertEqual(names.count(self.quiet_cafe.name), 1)
        self.assertEqual(names.count(self.loud_cafe.name), 1)


class PlaceViewLogTests(APITestCase):
    """
    [추가] SFR-005/SFR-007/DAR-002: 사용자가 장소 상세를 실제로 조회(선택)한 이력이
    추천 시스템의 행동 데이터(PlaceViewLog)로 남는지 확인.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='viewer01', password='pw12345678')
        self.place = Place.objects.create(name='조회테스트카페', address='대전 유성구')

    def test_authenticated_view_is_logged(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('place-detail', args=[self.place.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(PlaceViewLog.objects.filter(user=self.user, place=self.place).exists())

    def test_anonymous_view_is_not_logged(self):
        res = self.client.get(reverse('place-detail', args=[self.place.id]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PlaceViewLog.objects.count(), 0)

    def test_missing_place_does_not_error_or_log(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('place-detail', args=[99999]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(PlaceViewLog.objects.count(), 0)


class RecommendTests(APITestCase):
    """
    [고도화] SFR-005/SFR-007/DAR-002: 검색 기록뿐 아니라 실제로 선택(조회)한 장소의
    해시태그/업종/지역까지 반영한 추천이 로그인 사용자에게만 제공되는지 확인.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='recuser', password='pw12345678')

    def test_recommend_requires_login(self):
        res = self.client.get(reverse('search-recommend'))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recommend_no_history_returns_empty(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'], [])

    def test_recommend_uses_search_history(self):
        """[회귀 방지] 조회 이력이 아직 없어도 기존처럼 검색 키워드 매칭만으로 추천되어야 함."""
        place = Place.objects.create(name='유성 온천 카페', address='대전 유성구')
        SearchLog.objects.create(user=self.user, keyword='유성')
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend'))
        self.assertEqual(res.status_code, 200)
        names = [r['name'] for r in res.data['results']]
        self.assertIn(place.name, names)

    def test_recommend_uses_viewed_place_keywords(self):
        """[행동 패턴 축적] 실제로 선택한 장소와 키워드(위치/종류/분위기)가 겹치는 장소가 추천되어야 함."""
        viewed = Place.objects.create(name='본가 한식당', address='대전 유성구 궁동', category='음식점>한식')
        for keyword_type, keyword in [('location', '대전 유성구'), ('category', '한식'), ('mood', '데이트')]:
            PlaceKeyword.objects.create(place=viewed, keyword_type=keyword_type, keyword=keyword)
        PlaceViewLog.objects.create(user=self.user, place=viewed)

        similar = Place.objects.create(name='또다른 한식당', address='대전 유성구 어은동', category='음식점>한식')
        for keyword_type, keyword in [('location', '대전 유성구'), ('category', '한식')]:
            PlaceKeyword.objects.create(place=similar, keyword_type=keyword_type, keyword=keyword)

        unrelated = Place.objects.create(name='별다방', address='서울 강남구', category='카페>디저트')
        PlaceKeyword.objects.create(place=unrelated, keyword_type='category', keyword='디저트')

        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend'))

        names = [r['name'] for r in res.data['results']]
        self.assertIn(similar.name, names)
        self.assertNotIn(unrelated.name, names)
        # 이미 조회한(선택한) 장소 자체는 다시 추천되지 않아야 함
        self.assertNotIn(viewed.name, names)

    def test_recommend_excludes_already_viewed_places(self):
        viewed = Place.objects.create(name='이미본곳', address='대전 유성구')
        PlaceViewLog.objects.create(user=self.user, place=viewed)
        SearchLog.objects.create(user=self.user, keyword='이미본곳')

        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend'))
        names = [r['name'] for r in res.data['results']]
        self.assertNotIn('이미본곳', names)


class KeywordSearchLogTests(APITestCase):
    def test_keyword_search_logs_only_authenticated_user(self):
        url = reverse('elastic-search')
        self.client.get(url, {'search': '봉명동'})
        self.assertEqual(SearchLog.objects.count(), 0)

        user = User.objects.create_user(username='searcher01', password='pw12345678')
        self.client.force_authenticate(user=user)
        self.client.get(url, {'search': '봉명동'})
        self.assertEqual(SearchLog.objects.get().user, user)


class DailyRecommendViewTests(APITestCase):
    """[오늘의 추천 장소] GET /search/recommend/daily/ 엔드포인트 확인."""

    def setUp(self):
        self.user = User.objects.create_user(username='dailyviewuser', password='pw12345678')

    def test_requires_login(self):
        res = self.client.get(reverse('search-recommend-daily'))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_history_returns_message_and_null_results(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend-daily'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results'], {'식당': None, '카페': None, '술집': None})
        self.assertIn('message', res.data)

    def test_returns_korean_keyed_results_by_type(self):
        cafe = Place.objects.create(name='추천카페', address='대전 유성구 궁동', category='카페')
        PlaceKeyword.objects.create(place=cafe, keyword_type='location', keyword='대전 유성구')
        PlaceKeyword.objects.create(place=cafe, keyword_type='category', keyword='카페')
        SearchLog.objects.create(user=self.user, keyword='대전 유성구')

        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('search-recommend-daily'))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['results']['카페']['name'], '추천카페')
        self.assertIsNone(res.data['results']['식당'])
        self.assertIsNone(res.data['results']['술집'])
        self.assertNotIn('message', res.data)


class RecommendationHelperTests(TestCase):
    """api/recommendation.py의 순수 헬퍼 함수 단위 테스트 (키워드 집합/지역/업종 파싱)."""

    def test_place_keyword_set_merges_all_types(self):
        place = Place.objects.create(name='키워드카페', address='대전 유성구')
        PlaceKeyword.objects.create(place=place, keyword_type='location', keyword='대전 유성구')
        PlaceKeyword.objects.create(place=place, keyword_type='category', keyword='카페')
        PlaceKeyword.objects.create(place=place, keyword_type='mood', keyword='데이트')

        self.assertEqual(recommendation.place_keyword_set(place), {'대전 유성구', '카페', '데이트'})

    def test_place_keyword_set_empty_when_no_keywords(self):
        place = Place.objects.create(name='키워드없는카페', address='대전 유성구')
        self.assertEqual(recommendation.place_keyword_set(place), set())

    def test_region_hint_uses_first_two_tokens(self):
        self.assertEqual(recommendation.region_hint('대전 유성구 궁동로 123'), '대전 유성구')
        self.assertEqual(recommendation.region_hint('대전'), '대전')
        self.assertEqual(recommendation.region_hint(''), '')
        self.assertEqual(recommendation.region_hint(None), '')

    def test_neighborhood_hint_uses_third_token(self):
        self.assertEqual(recommendation.neighborhood_hint('대전 유성구 궁동 123-4'), '궁동')
        self.assertEqual(recommendation.neighborhood_hint('대전 유성구'), '')  # 토큰 2개뿐 -> 신호 없음
        self.assertEqual(recommendation.neighborhood_hint('대전 유성구 궁동로 123'), '')  # 도로명은 제외
        self.assertEqual(recommendation.neighborhood_hint('대전 유성구 123-4'), '')  # 숫자 섞인 토큰은 제외
        self.assertEqual(recommendation.neighborhood_hint(''), '')
        self.assertEqual(recommendation.neighborhood_hint(None), '')

    def test_category_tokens_splits_hierarchy(self):
        self.assertEqual(recommendation.category_tokens('음식점>한식>한정식'), {'음식점', '한식', '한정식'})
        self.assertEqual(recommendation.category_tokens(''), set())
        self.assertEqual(recommendation.category_tokens(None), set())


class PlaceTypeClassificationTests(TestCase):
    """[오늘의 추천 장소] classify_place_type()이 category 토큰을 식당/카페/술집으로 올바르게 묶는지 확인."""

    def test_classifies_cafe(self):
        self.assertEqual(classify_place_type(recommendation.category_tokens('카페>디저트')), 'cafe')
        self.assertEqual(classify_place_type(recommendation.category_tokens('음식점>카페,디저트')), 'cafe')

    def test_classifies_restaurant(self):
        self.assertEqual(classify_place_type(recommendation.category_tokens('음식점>한식>한정식')), 'restaurant')

    def test_bar_nested_under_restaurant_is_classified_as_bar_not_restaurant(self):
        """네이버가 '음식점>이자카야'처럼 술집을 음식점 하위로 분류해도 술집으로 분류돼야 함."""
        self.assertEqual(classify_place_type(recommendation.category_tokens('음식점>이자카야')), 'bar')

    def test_unmatched_category_returns_none(self):
        self.assertIsNone(classify_place_type(recommendation.category_tokens('숙박>모텔')))
        self.assertIsNone(classify_place_type(set()))


class DailyRecommendationHelperTests(TestCase):
    """[오늘의 추천 장소] daily_recommended_places()의 선정 우선순위(동네 > 연관 키워드)와 광고 제외를 확인."""

    def setUp(self):
        self.user = User.objects.create_user(username='dailyuser', password='pw12345678')

    def _make_place(self, name, address, category, location_kw, mood_kw=None):
        place = Place.objects.create(name=name, address=address, category=category)
        PlaceKeyword.objects.create(place=place, keyword_type='location', keyword=location_kw)
        for token in recommendation.category_tokens(category):
            PlaceKeyword.objects.create(place=place, keyword_type='category', keyword=token)
        if mood_kw:
            PlaceKeyword.objects.create(place=place, keyword_type='mood', keyword=mood_kw)
        return place

    def test_no_search_history_returns_all_none(self):
        results, has_history = recommendation.daily_recommended_places(self.user)
        self.assertFalse(has_history)
        self.assertEqual(results, {'restaurant': None, 'cafe': None, 'bar': None})

    def test_location_match_takes_priority_over_keyword_match(self):
        """동네가 안 맞으면 연관 키워드가 아무리 많이 겹쳐도 동네가 맞는 후보를 앞지르지 못해야 함."""
        matching_region = self._make_place(
            '유성구카페', '대전 유성구 궁동', '카페', '대전 유성구',
        )
        matching_keywords_only = self._make_place(
            '강남조용한카페', '서울 강남구', '카페', '서울 강남구', mood_kw='조용한',
        )
        SearchLog.objects.create(user=self.user, keyword='대전 유성구')
        SearchLog.objects.create(user=self.user, keyword='조용한')
        SearchLog.objects.create(user=self.user, keyword='조용한')

        results, has_history = recommendation.daily_recommended_places(self.user)

        self.assertTrue(has_history)
        self.assertEqual(results['cafe'], matching_region)
        self.assertNotEqual(results['cafe'], matching_keywords_only)

    def test_keyword_match_used_as_tiebreaker_within_same_location(self):
        same_region_plain = self._make_place('평범카페', '대전 유성구 궁동', '카페', '대전 유성구')
        same_region_matching_mood = self._make_place(
            '조용카페', '대전 유성구 궁동', '카페', '대전 유성구', mood_kw='조용한',
        )
        SearchLog.objects.create(user=self.user, keyword='대전 유성구')
        SearchLog.objects.create(user=self.user, keyword='조용한')

        results, has_history = recommendation.daily_recommended_places(self.user)

        self.assertTrue(has_history)
        self.assertEqual(results['cafe'], same_region_matching_mood)

    def test_ad_flagged_place_can_still_be_recommended(self):
        ad_cafe = self._make_place('광고카페', '대전 유성구 궁동', '카페', '대전 유성구')
        PlaceAnalysis.objects.create(
            name=ad_cafe.name, content_text='협찬', is_ad=True, ad_probability=90, ai_summary='광고'
        )
        SearchLog.objects.create(user=self.user, keyword='대전 유성구')

        results, has_history = recommendation.daily_recommended_places(self.user)

        self.assertTrue(has_history)
        self.assertEqual(results['cafe'], ad_cafe)

    def test_returns_one_place_per_type(self):
        self._make_place('식당1', '대전 유성구', '음식점>한식', '대전 유성구')
        self._make_place('카페1', '대전 유성구', '카페', '대전 유성구')
        self._make_place('술집1', '대전 유성구', '음식점>이자카야', '대전 유성구')
        SearchLog.objects.create(user=self.user, keyword='대전 유성구')

        results, has_history = recommendation.daily_recommended_places(self.user)

        self.assertTrue(has_history)
        self.assertEqual(results['restaurant'].name, '식당1')
        self.assertEqual(results['cafe'].name, '카페1')
        self.assertEqual(results['bar'].name, '술집1')


def _fake_response(status_code, json_data=None):
    resp = Mock()
    resp.status_code = status_code
    resp.json = Mock(return_value=json_data or {})
    return resp


def _query_param(url, key='query'):
    from urllib.parse import parse_qs, urlparse
    return parse_qs(urlparse(url).query).get(key, [''])[0]




@override_settings(NAVER_CLIENT_ID='dummy-id', NAVER_CLIENT_SECRET='dummy-secret')
class NaverPlaceDiscoveryTests(TestCase):
    """
    DAR-001/DAR-004 크롤러 자동화·오류감소 검증 (장소 정보 수집 단계만).

    [로직 분리] mine_from_naver()는 이제 장소 정보(이름/주소/설명/사진)만 수집하고
    리뷰/광고 판별은 하지 않습니다 - 그 부분은 NaverReviewRefreshTests(아래)가 검증합니다.
    - 신규 장소는 이미지까지 수집, 이미 등록된 장소는 완전히 건너뜀(재수집 없음)
    - 장소 1건 처리 중 예외가 나도 나머지 장소는 계속 처리됨
    - 일시적 5xx 응답은 재시도 후 성공 처리됨
    """

    def setUp(self):
        self.default_user = User.objects.create_user(username='crawler_bot', password='pw12345678')
        patcher = patch('api.naver_miner.time.sleep', return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _local_response(self, items):
        return _fake_response(200, {"items": items})

    @patch('api.naver_miner.get_exact_images_from_naver')
    @patch('api.naver_miner.requests.get')
    def test_new_place_creates_place_and_images_only(self, mock_get, mock_get_images):
        mock_get_images.return_value = ["http://img.example/1.jpg"]

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/local' in url:
                return self._local_response([
                    {"title": "진짜카페", "roadAddress": "대전 유성구 1번길", "category": "카페"}
                ])
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        new_places = naver_miner.mine_from_naver("유성 카페", request_interval=0)

        place = Place.objects.get(name="진짜카페")
        self.assertEqual(place.description, "카페")
        self.assertEqual(place.category, "카페")  # [추가] 추천 시스템용 업종 필드
        self.assertEqual(PlaceImage.objects.filter(place=place).count(), 1)
        self.assertEqual([p.name for p in new_places], ["진짜카페"])

        # [키워드 기반 장소 구분] 위치/종류 키워드는 주소·업종에서 AI 없이 바로 만들어져야 함
        location_keywords = set(place.keywords.filter(keyword_type='location').values_list('keyword', flat=True))
        category_keywords = set(place.keywords.filter(keyword_type='category').values_list('keyword', flat=True))
        self.assertEqual(location_keywords, {'대전 유성구'})
        self.assertEqual(category_keywords, {'카페'})
        self.assertFalse(place.keywords.filter(keyword_type='mood').exists())  # 분위기는 리뷰 최신화 때 채워짐

        # [로직 분리 회귀 테스트] 장소 수집 단계에서는 리뷰/광고 판별을 하지 않아야 함
        self.assertFalse(Review.objects.filter(place=place).exists())
        self.assertFalse(PlaceAnalysis.objects.filter(name="진짜카페").exists())
        blog_calls = [c for c in mock_get.call_args_list if 'search/v1/blog' in c.args[0]]
        self.assertEqual(len(blog_calls), 0)

    @patch('api.naver_miner.get_exact_images_from_naver')
    @patch('api.naver_miner.requests.get')
    def test_local_search_paginates_past_5_per_page(self, mock_get, mock_get_images):
        """
        [키워드당 수집 개수 확대] 지역 검색 API는 한 페이지에 최대 5건만 주므로, 13건을
        요청하면 start=1(5건)+start=6(5건)+start=11(3건, 5건 미만이라 여기서 중단)으로
        총 3번 페이지 요청을 보내 13곳을 모두 수집해야 합니다.
        """
        mock_get_images.return_value = []

        page1 = [{"title": f"장소{i}", "roadAddress": "대전 유성구"} for i in range(1, 6)]
        page2 = [{"title": f"장소{i}", "roadAddress": "대전 유성구"} for i in range(6, 11)]
        page3 = [{"title": f"장소{i}", "roadAddress": "대전 유성구"} for i in range(11, 14)]  # 3건 (마지막 페이지)
        local_pages_by_start = {'1': page1, '6': page2, '11': page3}

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/local' in url:
                start = _query_param(url, 'start') or '1'
                display = int(_query_param(url, 'display'))
                self.assertLessEqual(display, 5, "지역 검색 display는 5를 넘으면 안 됨")
                return self._local_response(local_pages_by_start.get(start, []))
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        naver_miner.mine_from_naver("유성구 장소", request_interval=0, max_places_per_keyword=20)

        self.assertEqual(Place.objects.count(), 13)
        local_calls = [c for c in mock_get.call_args_list if 'search/v1/local' in c.args[0]]
        self.assertEqual(len(local_calls), 3)  # start=1, 6, 11 세 페이지만 호출되고 멈춰야 함

    @patch('api.naver_miner.get_exact_images_from_naver')
    @patch('api.naver_miner.requests.get')
    def test_local_search_stops_early_when_start_returns_duplicate_page(self, mock_get, mock_get_images):
        """
        [중복 페이지 감지] 네이버 지역 검색 API가 start 파라미터를 무시하고 항상 같은
        첫 페이지를 되돌려주는 경우(실제 NAVER API HUB에서 확인된 동작), 두 번째 페이지가
        직전 페이지와 완전히 동일하면 그 자리에서 즉시 멈춰야 합니다. 그렇지 않으면 같은
        결과를 --limit 만큼 계속 반복 요청하며 API 호출만 낭비하게 됩니다.
        """
        mock_get_images.return_value = []

        # start 값과 상관없이 항상 동일한 5건을 되돌려주는(=페이지네이션이 실제로 동작하지
        # 않는) 상황을 재현.
        same_page = [{"title": f"장소{i}", "roadAddress": "대전 유성구"} for i in range(1, 6)]

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/local' in url:
                return self._local_response(same_page)
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        naver_miner.mine_from_naver("유성구 장소", request_interval=0, max_places_per_keyword=50)

        # 실제 고유 장소는 5곳뿐이어야 하고,
        self.assertEqual(Place.objects.count(), 5)
        # start=1 페이지와 start=6에서 받은 페이지가 동일함을 확인한 뒤 바로 멈춰야 하므로
        # local 검색 호출은 2번만 발생해야 함(50/5=10번을 전부 호출하면 안 됨).
        local_calls = [c for c in mock_get.call_args_list if 'search/v1/local' in c.args[0]]
        self.assertEqual(len(local_calls), 2)

    @patch('api.naver_miner.get_exact_images_from_naver')
    @patch('api.naver_miner.requests.get')
    def test_existing_place_is_skipped_entirely(self, mock_get, mock_get_images):
        place = Place.objects.create(name="이미있는카페", address="대전 서구")
        PlaceImage.objects.create(place=place, image_url="http://old.jpg")

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/local' in url:
                return self._local_response([{"title": "이미있는카페", "roadAddress": "대전 서구"}])
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        new_places = naver_miner.mine_from_naver("이미있는카페", request_interval=0)

        # [이미 크롤링된 장소 제외] 이미지 재수집도, 리뷰 관련 처리도 전혀 일어나지 않아야 함
        self.assertEqual(new_places, [])
        mock_get_images.assert_not_called()
        self.assertEqual(PlaceImage.objects.filter(place=place).count(), 1)
        self.assertFalse(Review.objects.filter(place=place).exists())

    @patch('api.naver_miner.get_exact_images_from_naver')
    @patch('api.naver_miner.requests.get')
    def test_one_place_error_does_not_abort_the_batch(self, mock_get, mock_get_images):
        mock_get_images.side_effect = [Exception("이미지 API 오류"), []]
        mock_get.return_value = self._local_response([
            {"title": "문제카페", "roadAddress": "대전 동구"},
            {"title": "정상카페", "roadAddress": "대전 동구"},
        ])

        naver_miner.mine_from_naver("동구", request_interval=0)

        self.assertFalse(Place.objects.filter(name="문제카페").exists())
        self.assertTrue(Place.objects.filter(name="정상카페").exists())

    def test_request_with_retry_retries_on_5xx_then_succeeds(self):
        with patch('api.naver_miner.requests.get') as mock_get:
            mock_get.side_effect = [_fake_response(500), _fake_response(200, {"items": []})]
            result = naver_miner._request_with_retry("https://naverapihub.apigw.ntruss.com/search/v1/local?query=x", {})

        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)

    def test_missing_naver_credentials_returns_early(self):
        with override_settings(NAVER_CLIENT_ID='', NAVER_CLIENT_SECRET=''):
            with patch('api.naver_miner.requests.get') as mock_get:
                naver_miner.mine_from_naver("아무 키워드")
                mock_get.assert_not_called()


@override_settings(NAVER_CLIENT_ID='dummy-id', NAVER_CLIENT_SECRET='dummy-secret')
class NaverReviewRefreshTests(TestCase):
    """
    [리뷰 소스 확장 + 평균 점수 검증] DAR-001/DAR-004: 장소 하나당 블로그+카페글 여러 건을
    모아 평균 광고 확률을 매기는 refresh_existing_places()/_refresh_place_reviews()를 검증.
    - 블로그+카페글을 합쳐 여러 건을 모으고, 각 글의 ad_probability 평균으로 PlaceAnalysis 갱신
    - 화면에 노출되는 대표 리뷰는 평균에 가장 가까운 점수를 받은 글 1건
    - 이전과 완전히 동일한 글은 재분석하지 않고 이전 점수를 재사용(AI 호출 절약)
    - 후보 글을 하나도 못 찾으면 안내용 placeholder로 처리
    - refresh_existing_places는 지역 검색(local) API를 절대 호출하지 않음
    - only_new=True면 아직 분석되지 않은 장소만 대상으로 함
    """

    def setUp(self):
        self.default_user = User.objects.create_user(username='crawler_bot', password='pw12345678')
        patcher = patch('api.naver_miner.time.sleep', return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _items_response(self, items):
        return _fake_response(200, {"items": items})

    def _blog_only_response(self, items):
        def get_side_effect(url, headers=None, timeout=None):
            return self._items_response(items if 'search/v1/blog' in url else [])
        return get_side_effect

    @patch('api.naver_miner.requests.get')
    def test_collects_next_pages_and_neighborhood_query_until_enough(self, mock_get):
        place = Place.objects.create(name="표본카페", address="대전 유성구 봉명동 1")
        requested = []

        def page(prefix, count, matching):
            return [{"title": f"표본카페 {prefix}{i}" if i < matching else f"다른곳 {prefix}{i}",
                     "description": "후기", "link": f"http://{prefix}/{i}"} for i in range(count)]

        def get_side_effect(url, headers=None, timeout=None):
            query, start = _query_param(url), _query_param(url, 'start') or '1'
            requested.append((url.split('/')[-1].split('?')[0], query, start))
            if 'search/v1/blog' not in url:
                return self._items_response([])
            if '봉명동' in query:
                return self._items_response(page('nb', 5, 5))
            if start == '1':
                return self._items_response(page('p1', 100, 10))
            if start == '101':
                return self._items_response(page('p2', 30, 10))
            return self._items_response([])

        mock_get.side_effect = get_side_effect
        selected, _ = naver_miner._collect_review_source_candidates(place, {}, 0)

        self.assertEqual(len(selected), 25)
        blog_starts = [(q, s) for kind, q, s in requested if kind == 'blog']
        self.assertIn(('표본카페 대전 유성구', '101'), blog_starts)
        self.assertNotIn(('표본카페 대전 유성구', '201'), blog_starts)
        self.assertIn(('표본카페 봉명동', '1'), blog_starts)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_fewer_than_refreshes_only_places_short_of_reviews(self, mock_get, mock_analyze, mock_mood):
        short = Place.objects.create(name="부족카페", address="대전 유성구")
        enough = Place.objects.create(name="충분카페", address="대전 유성구")
        for n in range(5):
            ReviewSource.objects.create(place=enough, source_type='blog', url=f'http://e/{n}',
                                        content_text=f'글{n}', ad_probability=10)
        mock_get.side_effect = lambda url, headers=None, timeout=None: self._items_response([])
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 50, 'reason': '안내'}

        naver_miner.refresh_existing_places(request_interval=0, fewer_than=5)

        searched = {_query_param(c.args[0]) for c in mock_get.call_args_list}
        self.assertEqual(searched, {'부족카페 대전 유성구'})
        self.assertEqual(enough.review_sources.count(), 5)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_failed_source_is_reanalyzed_but_judged_source_is_reused(self, mock_get, mock_analyze, mock_mood):
        place = Place.objects.create(name="테스트카페", address="대전 유성구")
        items = [
            {"title": "테스트카페 실패글", "description": "본문", "link": "http://blog.example/failed"},
            {"title": "테스트카페 정상글", "description": "본문", "link": "http://blog.example/judged"},
        ]
        ReviewSource.objects.create(
            place=place, source_type='blog', url=items[0]['link'], ad_probability=50, analysis_failed=True,
            content_text=f"[{items[0]['title']}] {items[0]['description']}",
        )
        ReviewSource.objects.create(
            place=place, source_type='blog', url=items[1]['link'], ad_probability=20,
            content_text=f"[{items[1]['title']}] {items[1]['description']}",
        )
        mock_get.side_effect = self._blog_only_response(items)
        mock_analyze.return_value = {'is_ad': True, 'non_ad_probability': 20, 'reason': '재분석'}

        naver_miner.refresh_existing_places(request_interval=0, only_failed=True)

        mock_analyze.assert_called_once()
        retried = place.review_sources.get(url=items[0]['link'])
        self.assertEqual(retried.ad_probability, 80)
        self.assertFalse(retried.analysis_failed)
        self.assertEqual(PlaceAnalysis.objects.get(name=place.name).ad_probability, 50)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_failed_source_is_stored_flagged_and_left_out_of_average(self, mock_get, mock_analyze, mock_mood):
        place = Place.objects.create(name="테스트카페", address="대전 유성구")
        items = [
            {"title": "테스트카페 글1", "description": "본문", "link": "http://blog.example/1"},
            {"title": "테스트카페 글2", "description": "본문", "link": "http://blog.example/2"},
        ]
        mock_get.side_effect = self._blog_only_response(items)
        mock_analyze.side_effect = [
            {'is_ad': True, 'non_ad_probability': 10, 'reason': '광고'},
            {'is_ad': False, 'non_ad_probability': 50, 'reason': '오류', 'analysis_failed': True},
        ]

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertEqual(PlaceAnalysis.objects.get(name=place.name).ad_probability, 90)
        self.assertTrue(place.review_sources.get(url=items[1]['link']).analysis_failed)
        self.assertFalse(place.review_sources.get(url=items[0]['link']).analysis_failed)

    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_depleted_credits_stop_run_and_keep_existing_data(self, mock_get, mock_analyze):
        place = Place.objects.create(name="테스트카페", address="대전 유성구")
        item = {"title": "테스트카페 글", "description": "본문", "link": "http://blog.example/1"}
        ReviewSource.objects.create(
            place=place, source_type='blog', url=item['link'], ad_probability=50, analysis_failed=True,
            content_text=f"[{item['title']}] {item['description']}",
        )
        Place.objects.create(name="다음카페", address="대전 유성구")
        mock_get.side_effect = self._blog_only_response([item])
        mock_analyze.return_value = {
            'is_ad': False, 'non_ad_probability': 50, 'reason': '오류',
            'analysis_failed': True, 'credits_depleted': True,
        }

        with self.assertRaises(naver_miner.GeminiCreditsDepleted):
            naver_miner.refresh_existing_places(request_interval=0, only_failed=True)

        mock_analyze.assert_called_once()
        self.assertTrue(place.review_sources.get().analysis_failed)
        self.assertFalse(PlaceAnalysis.objects.filter(name=place.name).exists())

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_collects_multiple_sources_and_averages_score(self, mock_get, mock_analyze, mock_mood):
        place = Place.objects.create(name="테스트카페", address="대전 유성구")

        blog_items = [
            {"title": f"테스트카페 블로그{i}", "description": f"블로그본문{i}", "link": f"http://blog.example/{i}"}
            for i in range(6)
        ]
        cafe_items = [
            {"title": f"테스트카페 카페글{i}", "description": f"카페본문{i}", "link": f"http://cafe.example/{i}"}
            for i in range(6)
        ]
        blog_values = [10, 20, 30, 40, 50, 60]
        cafe_values = [70, 80, 90, 15, 25, 35]

        ad_prob_by_content = {}
        for item, v in zip(blog_items, blog_values):
            ad_prob_by_content[f"[{item['title']}] {item['description']}"] = v
        for item, v in zip(cafe_items, cafe_values):
            ad_prob_by_content[f"[{item['title']}] {item['description']}"] = v

        def analyze_side_effect(content, place_name=None):
            v = ad_prob_by_content[content]
            return {'is_ad': v >= 70, 'non_ad_probability': 100 - v, 'reason': f'reason-{v}'}

        mock_analyze.side_effect = analyze_side_effect

        def get_side_effect(url, headers=None, timeout=None):
            self.assertNotIn('search/v1/local', url)
            if 'search/v1/blog' in url:
                return self._items_response(blog_items)
            if 'search/v1/cafearticle' in url:
                return self._items_response(cafe_items)
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        all_values = blog_values + cafe_values
        expected_avg = round(sum(all_values) / len(all_values))
        ad_threshold = getattr(settings, 'AD_EXCLUDE_THRESHOLD', 70)

        analysis = PlaceAnalysis.objects.get(name="테스트카페")
        self.assertEqual(analysis.ad_probability, expected_avg)
        self.assertEqual(analysis.is_ad, expected_avg >= ad_threshold)

        # 대표 리뷰는 평균에 가장 가까운 점수를 받은 글이어야 함
        content_by_value = {v: c for c, v in ad_prob_by_content.items()}
        expected_representative_value = min(all_values, key=lambda v: abs(v - expected_avg))
        expected_content = content_by_value[expected_representative_value]
        review = Review.objects.get(place=place, user=self.default_user)
        self.assertEqual(review.content, expected_content)

        # 소스 12건(블로그 6 + 카페글 6) 모두 ReviewSource로 저장되어야 함(15건 상한 이하)
        self.assertEqual(ReviewSource.objects.filter(place=place).count(), 12)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_reuses_previous_analysis_for_unchanged_sources(self, mock_get, mock_analyze, mock_mood):
        place = Place.objects.create(name="재사용카페", address="대전 중구")
        ReviewSource.objects.create(
            place=place, source_type='blog', title='재사용카페 블로그0',
            url='http://blog.example/0', content_text='[재사용카페 블로그0] 예전 그대로인 본문',
            is_ad=False, ad_probability=20,
        )

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "재사용카페 블로그0", "description": "예전 그대로인 본문", "link": "http://blog.example/0"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        # 완전히 동일한 글이므로 Gemini 재분석을 호출하지 않고 이전 점수(20)를 그대로 재사용해야 함
        mock_analyze.assert_not_called()
        analysis = PlaceAnalysis.objects.get(name="재사용카페")
        self.assertEqual(analysis.ad_probability, 20)
        self.assertEqual(ReviewSource.objects.filter(place=place).count(), 1)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_falls_back_to_placeholder_when_no_sources_found(self, mock_get, mock_analyze, mock_mood):
        Place.objects.create(name="언급없는카페", address="대전 대덕구")
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 50, 'reason': '분석할 리뷰를 찾지 못함'}

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url or 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        mock_analyze.assert_called_once_with("네이버 등록 인증 업체 정보입니다.")
        review = Review.objects.get(place__name="언급없는카페", user=self.default_user)
        self.assertEqual(review.content, "네이버 등록 인증 업체 정보입니다.")
        self.assertEqual(ReviewSource.objects.filter(place__name="언급없는카페").count(), 0)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_existing_places_never_calls_local_search(self, mock_get, mock_analyze, mock_mood):
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 60, 'reason': 'ok'}
        place_a = Place.objects.create(name="가맛집", address="대전 유성구")
        place_b = Place.objects.create(name="나맛집", address="대전 서구")

        # [오탐 매칭 완화] 검색어에 지역명이 함께 들어가므로(예: "가맛집 대전 유성구") 쿼리
        # 문자열도 그에 맞춰 매칭해야 함.
        content_map = {
            "가맛집 대전 유성구": [{"title": "가맛집 후기", "description": "가맛집 최신 후기", "link": "http://blog.example/a"}],
            "나맛집 대전 서구": [{"title": "나맛집 후기", "description": "나맛집 최신 후기", "link": "http://blog.example/b"}],
        }

        def side_effect(url, headers=None, timeout=None):
            self.assertNotIn('search/v1/local', url)
            if 'search/v1/blog' in url:
                return self._items_response(content_map.get(_query_param(url), []))
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertIn("가맛집 최신 후기", Review.objects.get(place=place_a, user=self.default_user).content)
        self.assertIn("나맛집 최신 후기", Review.objects.get(place=place_b, user=self.default_user).content)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_only_new_skips_already_analyzed_places(self, mock_get, mock_analyze, mock_mood):
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}
        analyzed_place = Place.objects.create(name="이미분석된곳", address="대전 유성구")
        PlaceAnalysis.objects.create(
            name="이미분석된곳", content_text="예전 분석", is_ad=False, ad_probability=10, ai_summary="이전"
        )
        new_place = Place.objects.create(name="새로등록된곳", address="대전 서구")

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "새로등록된곳 후기", "description": "새 리뷰 내용", "link": "http://blog.example/new"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        naver_miner.refresh_existing_places(request_interval=0, only_new=True)

        # 이미 PlaceAnalysis가 있는 장소는 건드리지 않고, 신규(미분석) 장소만 처리해야 함
        self.assertFalse(Review.objects.filter(place=analyzed_place).exists())
        self.assertTrue(Review.objects.filter(place=new_place).exists())

    @patch('api.naver_miner.extract_mood_keywords')
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_stores_mood_keywords_and_filters_disallowed_values(self, mock_get, mock_analyze, mock_mood):
        """[키워드 기반 장소 구분] AI가 고른 값 중 통제된 목록(MOOD_KEYWORDS) 밖의 값은 걸러야 함."""
        place = Place.objects.create(name="분위기카페", address="대전 유성구")
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}
        # 목록에 있는 값(MOOD_KEYWORDS[0], [1]) + 목록에 없는 값(상호명, 아무말)을 섞어서 반환
        mock_mood.return_value = [MOOD_KEYWORDS[0], MOOD_KEYWORDS[1], "분위기카페", "아무말"]

        def side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "분위기카페 후기", "description": "정말 좋았어요", "link": "http://blog.example/mood"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        mood_keywords = set(place.keywords.filter(keyword_type='mood').values_list('keyword', flat=True))
        self.assertEqual(mood_keywords, {MOOD_KEYWORDS[0], MOOD_KEYWORDS[1]})
        self.assertNotIn("분위기카페", mood_keywords)
        self.assertNotIn("아무말", mood_keywords)

    @patch('api.naver_miner.extract_mood_keywords')
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_skips_mood_reextraction_when_sources_unchanged(self, mock_get, mock_analyze, mock_mood):
        """리뷰 소스가 이전과 완전히 동일하면(전부 재사용) 분위기 키워드 AI 호출도 생략해야 함."""
        place = Place.objects.create(name="재사용무드카페", address="대전 중구")
        ReviewSource.objects.create(
            place=place, source_type='blog', title='재사용무드카페 블로그0',
            url='http://blog.example/0', content_text='[재사용무드카페 블로그0] 예전 그대로인 본문',
            is_ad=False, ad_probability=20,
        )
        PlaceKeyword.objects.create(place=place, keyword_type='mood', keyword=MOOD_KEYWORDS[0])

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "재사용무드카페 블로그0", "description": "예전 그대로인 본문", "link": "http://blog.example/0"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        mock_mood.assert_not_called()
        # 기존에 저장돼 있던 분위기 키워드가 그대로 유지되어야 함
        mood_keywords = set(place.keywords.filter(keyword_type='mood').values_list('keyword', flat=True))
        self.assertEqual(mood_keywords, {MOOD_KEYWORDS[0]})

    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_clears_mood_keywords_when_no_sources_found(self, mock_get, mock_analyze):
        """후보 글을 하나도 못 찾아 placeholder로 처리되는 경우, 낡은 분위기 키워드는 비워야 함."""
        place = Place.objects.create(name="이제조용한카페", address="대전 대덕구")
        PlaceKeyword.objects.create(place=place, keyword_type='mood', keyword=MOOD_KEYWORDS[0])
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 50, 'reason': '분석할 리뷰를 찾지 못함'}

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url or 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertFalse(place.keywords.filter(keyword_type='mood').exists())

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_backfills_location_and_category_keywords_for_legacy_places(
        self, mock_get, mock_analyze, mock_mood
    ):
        """[키워드 최신화 - 백필] 이 기능이 추가되기 전부터 있던 장소도 refresh 한 번으로 위치/종류 키워드가 채워져야 함."""
        legacy_place = Place.objects.create(
            name="레거시카페", address="대전 유성구 궁동", category="음식점>카페"
        )  # PlaceKeyword가 하나도 없는 상태 (예전에 만들어진 장소를 재현)
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "레거시카페 후기", "description": "좋았어요", "link": "http://blog.example/legacy"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        location_keywords = set(legacy_place.keywords.filter(keyword_type='location').values_list('keyword', flat=True))
        category_keywords = set(legacy_place.keywords.filter(keyword_type='category').values_list('keyword', flat=True))
        self.assertEqual(location_keywords, {'대전 유성구', '궁동'})
        self.assertEqual(category_keywords, {'음식점', '카페'})

    @patch('api.naver_miner.extract_mood_keywords')
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_extracts_mood_keywords_on_first_run_even_if_sources_reused(
        self, mock_get, mock_analyze, mock_mood
    ):
        """
        [키워드 최신화 - 백필] 이 기능이 추가되기 전부터 있던 장소는 ReviewSource가 이미
        현재 내용과 동일해(전부 재사용됨) 광고 재분석은 생략되더라도, 분위기 키워드가 아직
        하나도 없다면 분위기 키워드만은 최초 1회 반드시 새로 뽑아야 함.
        """
        place = Place.objects.create(name="레거시무드카페", address="대전 중구")
        ReviewSource.objects.create(
            place=place, source_type='blog', title='레거시무드카페 블로그0',
            url='http://blog.example/0', content_text='[레거시무드카페 블로그0] 예전 그대로인 본문',
            is_ad=False, ad_probability=20,
        )
        # PlaceKeyword(mood)는 의도적으로 만들지 않음 - 이 기능이 추가되기 전 상태를 재현
        mock_mood.return_value = [MOOD_KEYWORDS[0]]

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "레거시무드카페 블로그0", "description": "예전 그대로인 본문", "link": "http://blog.example/0"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        # 광고 재분석(analyze_review)은 여전히 생략되지만(내용 동일)
        mock_analyze.assert_not_called()
        # 분위기 키워드는 처음이라 반드시 호출되어야 함
        mock_mood.assert_called_once()
        mood_keywords = set(place.keywords.filter(keyword_type='mood').values_list('keyword', flat=True))
        self.assertEqual(mood_keywords, {MOOD_KEYWORDS[0]})

    def test_search_query_includes_region_to_reduce_coincidental_matches(self):
        """[오탐 매칭 완화] 검색어 자체에 지역명을 함께 넣어 네이버 검색 단계에서부터 무관한 글이 덜 걸리도록 해야 함."""
        place = Place.objects.create(name="알텐데", address="대전 유성구")
        seen_queries = []

        def get_side_effect(url, headers=None, timeout=None):
            seen_queries.append(_query_param(url))
            return self._items_response([])

        with patch('api.naver_miner.requests.get', side_effect=get_side_effect):
            naver_miner._collect_review_source_candidates(place, headers={}, request_interval=0)

        self.assertTrue(seen_queries)
        self.assertTrue(all(q == "알텐데 대전 유성구" for q in seen_queries))

    def test_extract_candidates_flags_match_tier_when_region_or_category_present(self):
        """[오탐 매칭 완화] 동네/지역/업종 키워드가 함께 언급된 글만 낮은(확실한) match_tier로 표시해야 함."""
        with patch('api.naver_miner.requests.get') as mock_get:
            mock_get.return_value = self._items_response([
                {"title": "알텐데 궁동 맛집", "description": "정말 좋았어요", "link": "http://blog.example/0"},
                {"title": "알텐데 대전 유성구 맛집", "description": "정말 좋았어요", "link": "http://blog.example/1"},
                {"title": "와이프도 알텐데", "description": "그냥 하는 말이었다", "link": "http://blog.example/2"},
            ])
            candidates, _ = naver_miner._extract_candidates_from_search(
                'blog', '알텐데 대전 유성구', {}, '알텐데',
                [(0, '궁동'), (1, '대전 유성구')],
            )

        self.assertEqual(len(candidates), 3)
        tier_by_title = {c["title"]: c["match_tier"] for c in candidates}
        self.assertEqual(tier_by_title["알텐데 궁동 맛집"], 0)
        self.assertEqual(tier_by_title["알텐데 대전 유성구 맛집"], 1)
        self.assertEqual(tier_by_title["와이프도 알텐데"], 3)

    def test_extract_candidates_excludes_non_review_posts(self):
        """[오탐 매칭 완화 3단계] 공고/모집/분양 등 리뷰가 아닌 글은 장소명이 언급돼도 후보에서 아예 제외해야 함."""
        with patch('api.naver_miner.requests.get') as mock_get:
            mock_get.return_value = self._items_response([
                {"title": "알텐데 방문 후기", "description": "정말 좋았어요", "link": "http://blog.example/1"},
                {"title": "알텐데 체험단 모집합니다", "description": "많은 신청 바랍니다", "link": "http://blog.example/2"},
                {"title": "알텐데 인근 오피스텔 분양", "description": "모델하우스 방문 예약", "link": "http://blog.example/3"},
            ])
            candidates, _ = naver_miner._extract_candidates_from_search(
                'blog', '알텐데', {}, '알텐데', []
            )

        titles = {c["title"] for c in candidates}
        self.assertEqual(titles, {"알텐데 방문 후기"})

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_excludes_coincidental_name_matches_when_enough_strict_sources_exist(
        self, mock_get, mock_analyze, mock_mood
    ):
        """
        [오탐 매칭 완화] "알텐데"라는 장소명이 흔한 어미와 겹쳐 "와이프도 알텐데"처럼 무관한
        글이 후보에 섞이더라도, 지역명까지 일치하는 확실한 매칭이 MAX_REVIEW_SOURCES(15)건
        이상이면 약한(무관할 수 있는) 매칭은 최종 리뷰 소스에서 잘려나가야 함.
        """
        place = Place.objects.create(name="알텐데", address="대전 유성구")
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}

        strict_items = [
            {
                "title": f"알텐데 대전 유성구 방문기{i}",
                "description": "정말 맛있었어요",
                "link": f"http://blog.example/strict{i}",
            }
            for i in range(naver_miner.MAX_REVIEW_SOURCES)
        ]
        coincidental_items = [
            {"title": "와이프도 알텐데", "description": "그냥 하는 말이었다", "link": "http://blog.example/coincidental"},
        ]

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response(strict_items + coincidental_items)
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        sources = ReviewSource.objects.filter(place=place)
        self.assertEqual(sources.count(), naver_miner.MAX_REVIEW_SOURCES)
        self.assertFalse(sources.filter(content_text__icontains="와이프도 알텐데").exists())

    def test_is_non_review_post_detects_common_patterns_without_flagging_real_reviews(self):
        """[오탐 매칭 완화 3단계] 공고/모집/분양 신호 문구가 있는 글만 True, 일반 후기 문구는 False여야 함."""
        self.assertTrue(naver_miner._is_non_review_post("맛집 체험단 모집합니다", "많은 신청 바랍니다"))
        self.assertTrue(naver_miner._is_non_review_post("신규 오피스텔 분양 안내", "모델하우스 방문 예약"))
        self.assertTrue(naver_miner._is_non_review_post("카페 아르바이트 모집", "시급 문의는 댓글로"))
        # 일반적인 후기 문구는 오탐(false positive)으로 걸러지면 안 됨
        self.assertFalse(naver_miner._is_non_review_post("정말 맛있었던 카페 후기", "분위기도 좋고 커피도 맛있어요"))
        self.assertFalse(naver_miner._is_non_review_post("이벤트 하길래 가봤어요", "친절하고 좋았습니다"))

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_never_scrapes_non_review_posts_even_when_place_name_mentioned(
        self, mock_get, mock_analyze, mock_mood
    ):
        """
        [오탐 매칭 완화 3단계] 장소명이 언급돼도 공고/체험단 모집/분양 정보 같은 글은
        AI 분석 단계로 넘어가기도 전에 후보에서 제외돼 ReviewSource로 저장되면 안 됨.
        """
        place = Place.objects.create(name="알텐데", address="대전 유성구")
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}

        blog_items = [
            {"title": "알텐데 방문 후기", "description": "정말 맛있었어요", "link": "http://blog.example/1"},
            {"title": "알텐데 체험단 모집합니다", "description": "많은 신청 바랍니다", "link": "http://blog.example/2"},
        ]
        cafe_items = [
            {"title": "알텐데 인근 오피스텔 분양", "description": "모델하우스 방문 예약", "link": "http://cafe.example/1"},
        ]

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response(blog_items)
            if 'search/v1/cafearticle' in url:
                return self._items_response(cafe_items)
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        sources = ReviewSource.objects.filter(place=place)
        self.assertEqual(sources.count(), 1)
        self.assertTrue(sources.filter(content_text__icontains="알텐데 방문 후기").exists())
        self.assertFalse(sources.filter(content_text__icontains="체험단 모집").exists())
        self.assertFalse(sources.filter(content_text__icontains="오피스텔 분양").exists())

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_prioritizes_neighborhood_match_over_different_branch_of_same_name(
        self, mock_get, mock_analyze, mock_mood
    ):
        """
        [오탐 매칭 완화 3단계 - 동명이점] 같은 상호가 같은 시/구 안에 다른 지점을 낼 수
        있으므로, 장소가 속한 동네(neighborhood_hint)까지 일치하는 글을 시/구만 일치하는
        (실제로는 다른 지점일 수 있는) 글보다 항상 먼저 채택해야 함.
        """
        place = Place.objects.create(name="동네카페", address="대전 유성구 궁동 123-4")
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok'}

        same_neighborhood_items = [
            {
                "title": f"동네카페 궁동점 방문기{i}",
                "description": "정말 맛있었어요",
                "link": f"http://blog.example/nbhd{i}",
            }
            for i in range(3)
        ]
        other_branch_items = [
            {
                "title": f"동네카페 대전 유성구 다른지점 방문기{i}",
                "description": "여기도 괜찮았어요",
                "link": f"http://blog.example/branch{i}",
            }
            for i in range(naver_miner.MAX_REVIEW_SOURCES)
        ]

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response(same_neighborhood_items + other_branch_items)
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        sources = ReviewSource.objects.filter(place=place)
        self.assertEqual(sources.count(), naver_miner.MAX_REVIEW_SOURCES)
        # 동네(궁동)까지 일치하는 소스가 전부 채택되어야 함
        for i in range(3):
            self.assertTrue(sources.filter(content_text__icontains=f"궁동점 방문기{i}").exists())

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_excludes_sources_without_place_info(self, mock_get, mock_analyze, mock_mood):
        """
        [오탐 매칭 완화 2단계] 장소명은 언급됐지만 그 장소에 대한 실질적인 정보가 없다고
        AI가 판정한(has_place_info=False) 글은 평균/대표 리뷰/ReviewSource 어디에도
        반영되지 않아야 함.
        """
        place = Place.objects.create(name="정보없는카페", address="대전 유성구")

        def analyze_side_effect(content, place_name=None):
            if '스치듯' in content:
                return {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok', 'has_place_info': False}
            return {'is_ad': False, 'non_ad_probability': 80, 'reason': 'ok', 'has_place_info': True}

        mock_analyze.side_effect = analyze_side_effect

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "정보없는카페 실제 후기", "description": "메뉴랑 분위기 정말 좋았어요", "link": "http://blog.example/real"},
                    {"title": "정보없는카페 스치듯 언급", "description": "그냥 지나가다 봤어요", "link": "http://blog.example/passing"},
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        sources = ReviewSource.objects.filter(place=place)
        self.assertEqual(sources.count(), 1)
        self.assertIn("메뉴랑 분위기", sources.first().content_text)
        review = Review.objects.get(place=place)
        self.assertIn("메뉴랑 분위기", review.content)

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_falls_back_to_placeholder_when_all_sources_lack_place_info(
        self, mock_get, mock_analyze, mock_mood
    ):
        """후보는 찾았지만 전부 정보성 없음으로 판정되면, 후보를 아예 못 찾은 경우와 동일하게 placeholder로 처리해야 함."""
        Place.objects.create(name="전부스치듯카페", address="대전 유성구")

        def analyze_side_effect(content, place_name=None):
            return {'is_ad': False, 'non_ad_probability': 90, 'reason': 'ok', 'has_place_info': False}

        mock_analyze.side_effect = analyze_side_effect

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "전부스치듯카페 언급", "description": "그냥 지나가다 봤어요", "link": "http://blog.example/passing"},
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertEqual(ReviewSource.objects.filter(place__name="전부스치듯카페").count(), 0)
        review = Review.objects.get(place__name="전부스치듯카페")
        self.assertEqual(review.content, "네이버 등록 인증 업체 정보입니다.")

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_reuses_has_place_info_for_unchanged_sources(self, mock_get, mock_analyze, mock_mood):
        """이전에 has_place_info=False로 판정된 글은 내용이 그대로면 재분석 없이 계속 제외돼야 함."""
        place = Place.objects.create(name="재사용정보카페", address="대전 중구")
        ReviewSource.objects.create(
            place=place, source_type='blog', title='재사용정보카페 스치듯',
            url='http://blog.example/0', content_text='[재사용정보카페 스치듯] 그냥 지나가다 봤어요',
            is_ad=False, ad_probability=10, has_place_info=False,
        )
        mock_analyze.return_value = {'is_ad': False, 'non_ad_probability': 50, 'reason': '분석할 리뷰를 찾지 못함'}

        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response([
                    {"title": "재사용정보카페 스치듯", "description": "그냥 지나가다 봤어요", "link": "http://blog.example/0"}
                ])
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})

        mock_get.side_effect = get_side_effect

        naver_miner.refresh_existing_places(request_interval=0)

        # 기존 소스와 완전히 동일한 내용이라 재분석하지 않고 이전 판정(has_place_info=False)을
        # 그대로 재사용해야 함 - analyze_review는 placeholder 안내 문구로 딱 한 번만 호출됨.
        mock_analyze.assert_called_once_with("네이버 등록 인증 업체 정보입니다.")
        self.assertEqual(ReviewSource.objects.filter(place=place).count(), 0)
        review = Review.objects.get(place=place)
        self.assertEqual(review.content, "네이버 등록 인증 업체 정보입니다.")

    def _blog_response_side_effect(self, items):
        def get_side_effect(url, headers=None, timeout=None):
            if 'search/v1/blog' in url:
                return self._items_response(items)
            if 'search/v1/cafearticle' in url:
                return self._items_response([])
            return _fake_response(404, {})
        return get_side_effect

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_excludes_non_reviews_but_keeps_verdict(self, mock_get, mock_analyze, mock_mood):
        """is_review=False인 글은 계산에서 빠지고, 사유와 함께 저장돼 재수집 때 재분석되지 않아야 함."""
        place = Place.objects.create(name="공고섞인카페", address="대전 유성구")

        def analyze_side_effect(content, place_name=None):
            if '함께 일하실' in content:
                return {
                    'is_ad': True, 'non_ad_probability': 0, 'reason': 'ok', 'has_place_info': True,
                    'is_review': False, 'exclude_reason': 'job_posting',
                }
            return {
                'is_ad': False, 'non_ad_probability': 80, 'reason': 'ok', 'has_place_info': True,
                'is_review': True, 'exclude_reason': None,
            }

        mock_analyze.side_effect = analyze_side_effect
        mock_get.side_effect = self._blog_response_side_effect([
            {"title": "공고섞인카페 후기", "description": "라떼가 맛있었어요", "link": "http://blog.example/real"},
            {"title": "공고섞인카페 소식", "description": "함께 일하실 분을 찾아요", "link": "http://blog.example/job"},
        ])

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertEqual(PlaceAnalysis.objects.get(name=place.name).ad_probability, 20)
        self.assertIn("라떼", Review.objects.get(place=place).content)
        self.assertIn("라떼", mock_mood.call_args[0][1])
        self.assertNotIn("함께 일하실", mock_mood.call_args[0][1])
        excluded = ReviewSource.objects.get(place=place, is_review=False)
        self.assertEqual(excluded.exclude_reason, 'job_posting')
        self.assertEqual(ReviewSource.objects.filter(place=place).count(), 2)

        mock_analyze.reset_mock()
        naver_miner.refresh_existing_places(request_interval=0)
        mock_analyze.assert_not_called()
        self.assertEqual(ReviewSource.objects.get(place=place, is_review=False).exclude_reason, 'job_posting')

    @patch('api.naver_miner.extract_mood_keywords', return_value=[])
    @patch('api.naver_miner.analyze_review')
    @patch('api.naver_miner.requests.get')
    def test_refresh_all_non_reviews_uses_placeholder_and_keeps_verdict(self, mock_get, mock_analyze, mock_mood):
        """전부 리뷰가 아니면 placeholder로 처리하되, 판정 기록은 남아야 함."""
        place = Place.objects.create(name="공고만있는카페", address="대전 유성구")

        def analyze_side_effect(content, place_name=None):
            return {
                'is_ad': False, 'non_ad_probability': 50, 'reason': 'ok', 'has_place_info': True,
                'is_review': False, 'exclude_reason': 'other_notice',
            }

        mock_analyze.side_effect = analyze_side_effect
        mock_get.side_effect = self._blog_response_side_effect([
            {"title": "공고만있는카페 안내", "description": "상가 임대 안내입니다", "link": "http://blog.example/n"},
        ])

        naver_miner.refresh_existing_places(request_interval=0)

        self.assertEqual(Review.objects.get(place=place).content, "네이버 등록 인증 업체 정보입니다.")
        self.assertEqual(ReviewSource.objects.get(place=place).exclude_reason, 'other_notice')


class AnalyzeReviewResponseNormalizationTests(TestCase):
    def _analyze(self, payload):
        with patch('api.gemini_service.genai') as mock_genai, \
                override_settings(GEMINI_API_KEY='dummy'):
            mock_genai.GenerativeModel.return_value.generate_content.return_value = Mock(text=json.dumps(payload))
            return analyze_review('본문', '테스트카페')

    def test_missing_is_review_is_not_filtered(self):
        result = self._analyze({'is_ad': False, 'non_ad_probability': 80, 'reason': 'ok'})
        self.assertTrue(result['is_review'])
        self.assertIsNone(result['exclude_reason'])

    def test_unknown_exclude_reason_becomes_other_notice(self):
        result = self._analyze({'is_review': False, 'exclude_reason': '이상한값'})
        self.assertFalse(result['is_review'])
        self.assertEqual(result['exclude_reason'], 'other_notice')

    def test_prompt_asks_for_review_verdict(self):
        with patch('api.gemini_service.genai') as mock_genai, \
                override_settings(GEMINI_API_KEY='dummy'):
            generate = mock_genai.GenerativeModel.return_value.generate_content
            generate.return_value = Mock(text='{}')
            analyze_review('본문', '테스트카페')
        prompt = generate.call_args[0][0]
        self.assertIn('"is_review"', prompt)
        self.assertIn('job_posting', prompt)


class AdminVerificationActionTests(TestCase):
    """
    [자체 학습 데이터셋 구축 1단계] admin의 "검증" 액션이 ReviewSource/PlaceKeyword에
    사람이 확정한 레이블(is_ad_verified/verified_is_ad, verified)을 올바르게 남기는지 확인.
    """

    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin01', password='pw12345678', is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)
        self.place = Place.objects.create(name='검증테스트카페', address='대전 유성구')

    def test_mark_review_source_verified_ad(self):
        source = ReviewSource.objects.create(
            place=self.place, source_type='blog', title='광고성 글', content_text='내용',
            is_ad=False, ad_probability=30,
        )
        self.client.post(
            reverse('admin:api_reviewsource_changelist'),
            {'action': 'mark_verified_ad', '_selected_action': [str(source.id)]},
        )
        source.refresh_from_db()
        self.assertTrue(source.is_ad_verified)
        self.assertTrue(source.verified_is_ad)
        self.assertIsNotNone(source.verified_at)
        self.assertEqual(source.verified_by, self.staff)

    def test_mark_review_source_verified_not_ad(self):
        source = ReviewSource.objects.create(
            place=self.place, source_type='blog', title='일반 글', content_text='내용',
            is_ad=True, ad_probability=70,
        )
        self.client.post(
            reverse('admin:api_reviewsource_changelist'),
            {'action': 'mark_verified_not_ad', '_selected_action': [str(source.id)]},
        )
        source.refresh_from_db()
        self.assertTrue(source.is_ad_verified)
        self.assertFalse(source.verified_is_ad)

    def test_mark_place_keyword_verified_correct_and_incorrect(self):
        correct_kw = PlaceKeyword.objects.create(place=self.place, keyword_type='mood', keyword=MOOD_KEYWORDS[0])
        incorrect_kw = PlaceKeyword.objects.create(place=self.place, keyword_type='mood', keyword=MOOD_KEYWORDS[1])

        self.client.post(
            reverse('admin:api_placekeyword_changelist'),
            {'action': 'mark_verified_correct', '_selected_action': [str(correct_kw.id)]},
        )
        self.client.post(
            reverse('admin:api_placekeyword_changelist'),
            {'action': 'mark_verified_incorrect', '_selected_action': [str(incorrect_kw.id)]},
        )

        correct_kw.refresh_from_db()
        incorrect_kw.refresh_from_db()
        self.assertTrue(correct_kw.verified)
        self.assertFalse(incorrect_kw.verified)


class ExportTrainingDataCommandTests(TestCase):
    """
    [자체 학습 데이터셋 구축 1단계] export_training_data 명령이 "검증된" 레이블만 골라
    jsonl 파일로 정확히 내보내는지 확인 (미검증 항목은 제외되어야 함).
    """

    def setUp(self):
        self.output_dir = tempfile.mkdtemp()
        self.place = Place.objects.create(name='데이터셋카페', address='대전 유성구')

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _read_jsonl(self, filename):
        path = os.path.join(self.output_dir, filename)
        with open(path, encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_export_only_includes_verified_ad_labels(self):
        ReviewSource.objects.create(
            place=self.place, source_type='blog', title='검증됨(광고)', content_text='내용A',
            url='http://a', is_ad_verified=True, verified_is_ad=True,
        )
        ReviewSource.objects.create(
            place=self.place, source_type='cafearticle', title='검증됨(광고아님)', content_text='내용B',
            url='http://b', is_ad_verified=True, verified_is_ad=False,
        )
        # 미검증 - 결과에 포함되면 안 됨
        ReviewSource.objects.create(
            place=self.place, source_type='blog', title='미검증', content_text='내용C',
            url='http://c',
        )

        call_command('export_training_data', output_dir=self.output_dir)

        rows = self._read_jsonl('ad_detection_dataset.jsonl')
        self.assertEqual(len(rows), 2)
        labels_by_text = {row['text']: row['label'] for row in rows}
        self.assertEqual(labels_by_text['내용A'], 'ad')
        self.assertEqual(labels_by_text['내용B'], 'not_ad')
        self.assertNotIn('내용C', labels_by_text)

    def test_export_mood_dataset_groups_by_place_with_correct_and_incorrect(self):
        ReviewSource.objects.create(
            place=self.place, source_type='blog', title='본문', content_text='분위기 좋은 카페입니다',
            url='http://a',
        )
        PlaceKeyword.objects.create(place=self.place, keyword_type='mood', keyword=MOOD_KEYWORDS[0], verified=True)
        PlaceKeyword.objects.create(place=self.place, keyword_type='mood', keyword=MOOD_KEYWORDS[1], verified=False)
        # 미검증 mood 키워드 - correct/incorrect 어디에도 들어가면 안 됨
        PlaceKeyword.objects.create(place=self.place, keyword_type='mood', keyword=MOOD_KEYWORDS[2])
        # 검증 안 된 장소는 결과에 아예 포함되지 않아야 함
        other_place = Place.objects.create(name='미검증장소', address='서울 강남구')
        PlaceKeyword.objects.create(place=other_place, keyword_type='mood', keyword=MOOD_KEYWORDS[0])

        call_command('export_training_data', output_dir=self.output_dir)

        rows = self._read_jsonl('mood_keywords_dataset.jsonl')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['place'], self.place.name)
        self.assertEqual(row['correct_keywords'], [MOOD_KEYWORDS[0]])
        self.assertEqual(row['incorrect_keywords'], [MOOD_KEYWORDS[1]])
        self.assertEqual(row['text'], '분위기 좋은 카페입니다')

    def test_export_with_no_verified_data_produces_empty_files(self):
        ReviewSource.objects.create(
            place=self.place, source_type='blog', title='미검증', content_text='아무 내용',
            url='http://a',
        )

        call_command('export_training_data', output_dir=self.output_dir)

        self.assertEqual(self._read_jsonl('ad_detection_dataset.jsonl'), [])
        self.assertEqual(self._read_jsonl('mood_keywords_dataset.jsonl'), [])


class ExportRecommendationDatasetCommandTests(TestCase):
    """
    [추천용 데이터셋 구축] export_recommendation_dataset 명령이 SearchLog(약한 신호)/
    PlaceViewLog(강한 신호)를 사용자-장소 상호작용 데이터셋(jsonl)으로 올바르게 정리하는지 확인.
    """

    def setUp(self):
        self.output_dir = tempfile.mkdtemp()
        self.user = User.objects.create_user(username='datasetuser', password='pw12345678')

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _read_jsonl(self, filename):
        path = os.path.join(self.output_dir, filename)
        with open(path, encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def _rows_by_place(self, filename, key='place_id'):
        return {row[key]: row for row in self._read_jsonl(filename)}

    def test_view_and_search_signals_produce_separate_weighted_rows(self):
        viewed_place = Place.objects.create(name='본가맛집', address='대전 유성구')
        searched_place = Place.objects.create(name='이디야', address='대전 서구', category='카페')
        PlaceKeyword.objects.create(place=searched_place, keyword_type='category', keyword='카페')

        PlaceViewLog.objects.create(user=self.user, place=viewed_place)
        SearchLog.objects.create(user=self.user, keyword='카페')

        call_command('export_recommendation_dataset', output_dir=self.output_dir)

        rows = self._rows_by_place('interactions.jsonl')
        self.assertEqual(rows[viewed_place.id]['view_count'], 1)
        self.assertEqual(rows[viewed_place.id]['search_match_count'], 0)
        self.assertEqual(rows[viewed_place.id]['weight'], recommendation.VIEW_WEIGHT)

        self.assertEqual(rows[searched_place.id]['view_count'], 0)
        self.assertEqual(rows[searched_place.id]['search_match_count'], 1)
        self.assertEqual(rows[searched_place.id]['weight'], recommendation.SEARCH_WEIGHT)

    def test_view_and_search_for_same_place_combine_into_one_row(self):
        place = Place.objects.create(name='둘다카페', address='대전 유성구', category='카페')
        PlaceKeyword.objects.create(place=place, keyword_type='category', keyword='카페')

        PlaceViewLog.objects.create(user=self.user, place=place)
        SearchLog.objects.create(user=self.user, keyword='카페')

        call_command('export_recommendation_dataset', output_dir=self.output_dir)

        rows = self._read_jsonl('interactions.jsonl')
        matching = [r for r in rows if r['place_id'] == place.id]
        self.assertEqual(len(matching), 1)  # 두 신호가 한 행으로 합쳐져야 함
        row = matching[0]
        self.assertEqual(row['view_count'], 1)
        self.assertEqual(row['search_match_count'], 1)
        self.assertEqual(row['weight'], recommendation.VIEW_WEIGHT + recommendation.SEARCH_WEIGHT)

    def test_user_with_no_activity_produces_no_rows(self):
        User.objects.create_user(username='inactiveuser', password='pw12345678')
        Place.objects.create(name='아무도안본카페', address='대전 유성구')

        call_command('export_recommendation_dataset', output_dir=self.output_dir)

        self.assertEqual(self._read_jsonl('interactions.jsonl'), [])

    def test_place_features_include_keyword_lists_by_type(self):
        place = Place.objects.create(name='특징카페', address='대전 유성구 궁동', category='카페')
        PlaceKeyword.objects.create(place=place, keyword_type='location', keyword='대전 유성구')
        PlaceKeyword.objects.create(place=place, keyword_type='category', keyword='카페')
        PlaceKeyword.objects.create(place=place, keyword_type='mood', keyword=MOOD_KEYWORDS[0])
        bare_place = Place.objects.create(name='키워드없는곳', address='서울')

        call_command('export_recommendation_dataset', output_dir=self.output_dir)

        rows = self._rows_by_place('place_features.jsonl')
        self.assertEqual(rows[place.id]['location_keywords'], ['대전 유성구'])
        self.assertEqual(rows[place.id]['category_keywords'], ['카페'])
        self.assertEqual(rows[place.id]['mood_keywords'], [MOOD_KEYWORDS[0]])
        self.assertEqual(rows[bare_place.id]['location_keywords'], [])
        self.assertEqual(rows[bare_place.id]['category_keywords'], [])
        self.assertEqual(rows[bare_place.id]['mood_keywords'], [])


class FrontendCompatibilityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='member01', password='StrongPass123')
        self.staff = User.objects.create_user(username='staff01', password='StrongPass123', is_staff=True)
        self.place = Place.objects.create(name='호환카페', address='대전 유성구', description='조용한 카페')

    def test_login_returns_token_and_is_staff(self):
        res = self.client.post(reverse('login'), {'id': 'staff01', 'password': 'StrongPass123'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['token'], res.data['access'])
        self.assertTrue(res.data['is_staff'])

    def test_signup_name_is_returned_on_login(self):
        self.client.post(reverse('signup'), {'id': 'named01', 'password': 'StrongPass123', 'first_name': '김범수'})
        res = self.client.post(reverse('login'), {'id': 'named01', 'password': 'StrongPass123'})
        self.assertEqual(res.data['user']['first_name'], '김범수')

    def test_staff_can_answer_inquiry(self):
        inquiry = Inquiry.objects.create(user=self.user, category='etc', message='문의합니다')
        url = reverse('admin-inquiry-answer', args=[inquiry.id])

        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.patch(url, {'answer': '답변'}).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.client.patch(url, {'answer': ''}).status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.patch(url, {'answer': '확인했습니다.'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['answer'], '확인했습니다.')
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.answer, '확인했습니다.')
        self.assertEqual(self.client.patch(reverse('admin-inquiry-answer', args=[9999]), {'answer': 'x'}).status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_inquiry_detail_is_owner_or_staff_only(self):
        inquiry = Inquiry.objects.create(user=self.user, category='etc', message='내 문의')
        other = User.objects.create_user(username='other01', password='StrongPass123')
        url = reverse('inquiry-detail', args=[inquiry.id])

        self.client.force_authenticate(user=other)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_user_cannot_set_answer_when_creating_inquiry(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(reverse('create-inquiry'), {'category': 'etc', 'message': '문의', 'answer': '셀프 답변'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Inquiry.objects.get().answer, '')

    def test_admin_endpoints_are_staff_only(self):
        names = ['admin-users', 'admin-places', 'admin-analysis', 'admin-reviews', 'admin-inquiries']
        for name in names:
            self.client.force_authenticate(user=None)
            self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_401_UNAUTHORIZED)
            self.client.force_authenticate(user=self.user)
            self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_403_FORBIDDEN)
            self.client.force_authenticate(user=self.staff)
            self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_200_OK)

    def test_keyword_search_returns_list_and_keeps_ad_flagged_places(self):
        res = self.client.get(reverse('elastic-search'), {'search': '호환카페'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([p['id'] for p in res.data], [self.place.id])

        PlaceAnalysis.objects.create(name='호환카페', content_text='광고', is_ad=True, ad_probability=95)
        res = self.client.get(reverse('elastic-search'), {'search': '호환카페'})
        self.assertEqual([p['id'] for p in res.data], [self.place.id])

    def test_recent_places_lists_latest_view_first_without_duplicates(self):
        second = Place.objects.create(name='두번째카페', address='대전 유성구')
        other = User.objects.create_user(username='other02', password='StrongPass123')
        url = reverse('recent-places')
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=other)
        self.client.get(reverse('place-detail', args=[second.id]))
        self.client.force_authenticate(user=self.user)
        for place in (self.place, second, self.place):
            self.client.get(reverse('place-detail', args=[place.id]))

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([p['id'] for p in res.data], [self.place.id, second.id])
        self.assertIn('viewed_at', res.data[0])
        self.assertEqual([p['id'] for p in self.client.get(url, {'limit': 1}).data], [self.place.id])

    def test_user_can_delete_only_own_review(self):
        other = User.objects.create_user(username='other03', password='StrongPass123')
        mine = Review.objects.create(place=self.place, user=self.user, content='내 리뷰', rating=4)
        theirs = Review.objects.create(place=self.place, user=other, content='남의 리뷰', rating=5)

        self.assertEqual(self.client.delete(reverse('review-delete', args=[mine.id])).status_code,
                         status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.delete(reverse('review-delete', args=[theirs.id])).status_code,
                         status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(reverse('review-delete', args=[mine.id])).status_code,
                         status.HTTP_204_NO_CONTENT)
        self.assertFalse(Review.objects.filter(id=mine.id).exists())
        self.assertTrue(Review.objects.filter(id=theirs.id).exists())

    @override_settings(NAVER_CLIENT_ID='dummy-id', NAVER_CLIENT_SECRET='dummy-secret')
    @patch('api.management.commands.fill_coordinates.time.sleep', return_value=None)
    @patch('api.naver_miner.requests.get')
    def test_fill_coordinates_saves_matching_item_only(self, mock_get, _sleep):
        self.place.address = '대전광역시 유성구 봉명로 1'
        self.place.save()
        unmatched = Place.objects.create(name='없는카페', address='대전광역시 유성구 봉명로 2')
        items = [{'title': '<b>호환카페</b>', 'roadAddress': '대전광역시 유성구 봉명로 1',
                  'mapx': '1273444321', 'mapy': '363578220'}]
        mock_get.side_effect = lambda url, headers=None, timeout=None: _fake_response(
            200, {'items': items if '%ED%98%B8%ED%99%98' in url else []})

        call_command('fill_coordinates', stdout=io.StringIO())

        self.place.refresh_from_db()
        unmatched.refresh_from_db()
        self.assertAlmostEqual(self.place.latitude, 36.357822)
        self.assertAlmostEqual(self.place.longitude, 127.3444321)
        self.assertIsNone(unmatched.latitude)

    def test_place_reviews_include_non_ad_sources_without_duplicates(self):
        crawler = User.objects.create_user(username='crawler01', password='StrongPass123')
        Review.objects.create(place=self.place, user=crawler, content='글0', rating=5)
        Review.objects.create(place=self.place, user=self.user, content='직접 쓴 리뷰', rating=4)
        for n, prob in enumerate([10, 90, 20, 30, 40, 50, 60], start=0):
            ReviewSource.objects.create(place=self.place, source_type='blog', url=f'http://b/{n}',
                                        title=f'제목{n}', content_text=f'글{n}', ad_probability=prob)
        ReviewSource.objects.create(place=self.place, source_type='blog', url='http://b/job',
                                    content_text='구인', ad_probability=5, is_review=False)

        res = self.client.get(reverse('place-reviews', args=[self.place.id]))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual([r['content'] for r in res.data if not r['is_external']], ['직접 쓴 리뷰'])
        external = [r for r in res.data if r['is_external']]
        self.assertEqual([r['content'] for r in external], ['글0', '글2', '글3', '글4', '글5'])
        self.assertEqual(external[0]['url'], 'http://b/0')
        self.assertIsNone(external[0]['rating'])

    def test_keyword_search_includes_review_counts(self):
        def source(n, **fields):
            ReviewSource.objects.create(place=self.place, source_type='blog', url=f'http://b/{n}',
                                        content_text=f'글{n}', **fields)
        source(1, ad_probability=10)
        source(2, ad_probability=90)
        source(3, ad_probability=70)
        source(4, ad_probability=95, is_review=False, exclude_reason='job_posting')
        source(5, ad_probability=50, analysis_failed=True)
        bare = Place.objects.create(name='호환카페 2호점', address='대전 유성구')

        res = self.client.get(reverse('elastic-search'), {'search': '호환카페'})
        by_id = {p['id']: p for p in res.data}
        self.assertEqual(
            {k: by_id[self.place.id][k] for k in ('review_total', 'ad_excluded', 'review_counted')},
            {'review_total': 3, 'ad_excluded': 2, 'review_counted': 1},
        )
        self.assertEqual(
            {k: by_id[bare.id][k] for k in ('review_total', 'ad_excluded', 'review_counted')},
            {'review_total': 0, 'ad_excluded': 0, 'review_counted': 0},
        )

    def test_place_detail_includes_analysis(self):
        res = self.client.get(reverse('place-detail', args=[self.place.id]))
        self.assertIsNone(res.data['non_ad_probability'])

        PlaceAnalysis.objects.create(name='호환카페', content_text='후기', ad_probability=20, ai_summary='실제 후기')
        res = self.client.get(reverse('place-detail', args=[self.place.id]))
        self.assertEqual(res.data['non_ad_probability'], 80)
        self.assertEqual(res.data['ai_filtering_reason'], '실제 후기')
