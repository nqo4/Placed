"""
Kakao(Daum) 이미지 검색 API로 "우리가 이미 이 장소의 후기로 확인한 글"에 실린 사진을 찾습니다.

이미지 검색 결과에는 사진이 실린 글 주소(doc_url)가 같이 옵니다. 그 주소가 이 장소의
ReviewSource(주소 대조로 수집하고 AI가 광고 아닌 실제 후기로 판정한 글)와 같으면, 이름이
같은 다른 가게의 사진이 섞일 걱정 없이 이 장소의 사진으로 볼 수 있습니다.
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

KAKAO_IMAGE_SEARCH_URL = 'https://dapi.kakao.com/v2/search/image'
KAKAO_IMAGE_SEARCH_SIZE = 80  # API 최대값
MIN_IMAGE_SIDE = 300  # 지도 캡처·아이콘 같은 작은 사진 제외
REQUEST_TIMEOUT = 6


def review_post_key(url):
    """같은 글을 가리키는 주소를 하나로 맞춥니다(네이버 블로그는 http/https·모바일·PostView 형식이 섞여 옴)."""
    url = url or ''
    m = (re.search(r'blog\.naver\.com/([^/?#]+)/(\d+)', url)
         or re.search(r'blog\.naver\.com/PostView\.\w+\?(?=.*blogId=([^&]+))(?=.*logNo=(\d+))', url))
    if m:
        return f'naver:{m.group(1).lower()}/{m.group(2)}'
    return re.sub(r'^https?://(m\.)?', '', url.split('#')[0].rstrip('/')).lower()


def verified_review_images(place, query, max_count=5):
    """
    query로 Kakao 이미지 검색을 하고, 이 장소의 광고 아닌 후기 글에 실린 사진만 돌려줍니다.
    키가 없거나 요청이 실패하면 빈 목록을 돌려줍니다(네이버 사진으로 채우므로 기존 사진을 지울 위험은 없음).
    """
    api_key = getattr(settings, 'KAKAO_REST_API_KEY', '')
    if not api_key:
        return []
    threshold = getattr(settings, 'AD_EXCLUDE_THRESHOLD', 70)
    review_urls = place.review_sources.filter(
        is_review=True, has_place_info=True, analysis_failed=False, ad_probability__lt=threshold
    ).values_list('url', flat=True)
    review_keys = {review_post_key(url) for url in review_urls}
    if not review_keys:
        return []

    try:
        response = requests.get(
            KAKAO_IMAGE_SEARCH_URL,
            params={'query': query, 'size': KAKAO_IMAGE_SEARCH_SIZE},
            headers={'Authorization': f'KakaoAK {api_key}'},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        documents = response.json().get('documents', [])
    except (requests.RequestException, ValueError) as exc:
        logger.warning("카카오 이미지 검색 실패: query=%s - %s", query, exc)
        return []

    links = []
    for doc in documents:
        link = doc.get('image_url')
        too_small = min(doc.get('width') or 0, doc.get('height') or 0) < MIN_IMAGE_SIDE
        if not link or link in links or too_small or review_post_key(doc.get('doc_url')) not in review_keys:
            continue
        links.append(link)
        if len(links) >= max_count:
            break
    return links
