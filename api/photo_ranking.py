"""
[대표 사진 고르기] 장소 사진 후보를 Gemini로 분류해, 검색 결과·추천 카드에 나오는 첫 사진이
음식·매장 사진이 되도록 순서를 정하고 관계없는 사진(스티커·지도·숙소 방 등)은 뺍니다.
"""
import io
import logging

import requests
from PIL import Image

from .gemini_service import classify_place_photos

logger = logging.getLogger(__name__)

# 카드 첫 장으로 좋은 순서: 음식 → 매장 내부·외관 → 메뉴판·인물. other는 버립니다.
LABEL_ORDER = {'food': 0, 'interior': 1, 'exterior': 1, 'menu': 2, 'people': 2}
DOWNLOAD_TIMEOUT = 6
MAX_SIDE = 512  # Gemini로 보낼 때 줄이는 크기(토큰·전송량 절약)


def _download(url):
    """사진을 받아 JPEG로 줄입니다. 받을 수 없으면 None."""
    try:
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert('RGB')
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=80)
        return buffer.getvalue()
    except Exception as exc:  # 네트워크·이미지 형식 오류 모두 "못 받음"으로 처리
        logger.info("사진 다운로드 실패: %s - %s", url, exc)
        return None


def rank_place_photos(place, links, max_count=5):
    """
    links를 대표 사진 순서로 정렬해 max_count장까지 돌려줍니다.
    - 음식 → 내부·외관 → 메뉴판·인물 순, 같은 순위 안에서는 원래 순서(후기 글 사진 우선)를 지킵니다.
    - other로 분류된 사진은 뺍니다.
    - 서버에서 받지 못한 사진은 판단할 수 없어 맨 뒤에 둡니다(브라우저에서는 보일 수 있음).
    - Gemini 호출이 실패하면 원래 순서 그대로 돌려줘 사진을 잃지 않습니다.
    """
    downloaded = [(link, _download(link)) for link in links]
    checked = [(link, data) for link, data in downloaded if data]
    unchecked = [link for link, data in downloaded if not data]
    if not checked:
        return links[:max_count]

    labels = classify_place_photos(place.name, place.category, [('image/jpeg', data) for _, data in checked])
    if labels is None:
        return links[:max_count]

    kept = [(LABEL_ORDER[label], i, link) for i, ((link, _), label) in enumerate(zip(checked, labels))
            if label in LABEL_ORDER]
    ranked = [link for _, _, link in sorted(kept)] + unchecked
    return ranked[:max_count]
