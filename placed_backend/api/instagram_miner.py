import requests
import re
import time
import random
import instaloader
from api.models import Place, Review, User

def insert_mock_data():
    try:
        default_user = User.objects.get(id=1)
    except User.DoesNotExist:
        default_user = User.objects.first()

    # AI가 광고성과 진짜 리뷰를 구별할 수 있도록 정교하게 짠 샘플 데이터
    mock_reviews = [
        {"place": "둔산동 소소네 조개구이", "content": "📍 대전 둔산동 맛집 추천! #협찬 받았지만 솔직하게 작성합니다. 조개 알이 정말 실하고 신선해요! 분위기도 좋아서 회식 장소로 강추합니다. #둔산동맛집 #대전조개구이"},
        {"place": "유성 카피바라 카페", "content": "내돈내산 유성 신상 카페 투어. 커피는 산미가 강한 편이고 디저트는 무난함. 주차가 너무 힘들어서 재방문 의사는 글쎄... #유성카페 #대전카페"},
        {"place": "궁동 대박마라탕", "content": "📍궁동 대박마라탕 [서비스 제공] 매운맛 2단계 딱 적당함! 꿔바로우 소스가 새콤달콤해서 완전 중독성 대박이에요. 다들 꼭 가보세요 #궁동맛집 #어린이회관맛집"},
        {"place": "은행동 감성분식", "content": "친구들이랑 다녀온 은행동 떡볶이집. 옛날 초등학교 앞 떡볶이 맛이라 추억 돋고 좋았음. 튀김이 바삭해서 마음에 듦."},
    ]

    for item in mock_reviews:
        place, created = Place.objects.get_or_create(
            name=item["place"],
            defaults={
                'address': "대전광역시 유성구 대학로",
                'description': "테스트용 인스타그램 수집 데이터"
            }
        )
        
        Review.objects.create(
            place=place,
            user=default_user,
            content=item["content"],
            rating=5
        )
        print(f"테스트 데이터 생성 완료: [{place.name}]")

    print("모든 가짜 데이터가 성공적으로 데이터베이스에 저장되었습니다.")

def mine_places_by_hashtags():
    L = instaloader.Instaloader()
    
    # 크롬 sessionid 쿠키 주입
    INSTA_SESSION_ID = "30541486478%3Aj7Vgcy97mshdyk%3A19%3AAYhcK5JRsF9-2IeWQ4bheAsV0od6kMOquf232cc8twA"
    
    print("세션 쿠키 직접 주입으로 인스타 보안 우회 중...")
    try:
        L.context._session.cookies.set("sessionid", INSTA_SESSION_ID, domain=".instagram.com")
        profile = instaloader.Profile.from_username(L.context, "placed_ch12")
        print(f"로그인 검증 완료! [{profile.username}] 계정으로 인증되었습니다.")
    except Exception as e:
        print(f"쿠키 주입 실패: {e}")
        return

    # 타겟 해시태그 리스트
    target_hashtags = ["대전카페", "유성카페", "둔산동카페"]
    
    try:
        default_user = User.objects.get(id=1)
    except User.DoesNotExist:
        default_user = User.objects.first()

    # 인스타 서버의 필터링을 피하기 위해 브라우저 위장 헤더를 보강합니다.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-IG-App-ID": "936619743392459",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.instagram.com/"
    }

    for hashtag_name in target_hashtags:
        print(f"[{hashtag_name}] 기반 장소 채굴 시작...")
        
        # 인스타그램 공식 웹 해시태그 검색 API 주소 직접 타격
        url = f"https://www.instagram.com/api/v1/tags/web_info/?tag_name={hashtag_name}"
        
        try:
            # instaloader가 로그인에 성공한 세션을 그대로 빌려와서 직접 요청을 보냅니다.
            response = L.context._session.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"   {hashtag_name} 요청 거절됨 (상태코드: {response.status_code})")
                time.sleep(10)
                continue
                
            data = response.json()
            
            # 인스타 서버가 돌려준 JSON 데이터 구조에서 최신 게시글 뭉치 추출
            sections = data.get("data", {}).get("recent", {}).get("sections", [])
            
            count = 0
            for section in sections:
                layout_content = section.get("layout_content", {})
                medias = layout_content.get("medias", [])
                
                for media_wrapper in medias:
                    media = media_wrapper.get("media", {})
                    
                    # 본문 텍스트 추출
                    caption = media.get("caption", {})
                    content = caption.get("text", "") if caption else ""
                    
                    if not content:
                        continue
                        
                    if count >= 10:
                        break
                    
                    # 장소 이름 추출 로직
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    if not lines:
                        continue
                    
                    place_name = lines[0]
                    location_match = re.search(r'📍\s*([가-힣a-zA-Z0-9\s]+)', content)
                    if location_match:
                        place_name = location_match.group(1).strip()
                    
                    place_name = place_name[:30]
                    
                    # DB 저장
                    place, created = Place.objects.get_or_create(
                        name=place_name,
                        defaults={
                            'address': f"대전 어딘가 (태그: #{hashtag_name})",
                            'description': f"인스타그램 #{hashtag_name} 직접 수집 데이터"
                        }
                    )
                    
                    Review.objects.create(
                        place=place,
                        user=default_user,
                        content=content,
                        rating=5
                    )
                    print(f"   ▶ 수집 완료: [{place.name}]")
                    count += 1
                    
                    # 속도 제한 방지 대기 (3~7초 랜덤)
                    time.sleep(random.uniform(7.0, 10.0))
                    
                if count >= 10:
                    break
                    
            if count == 0:
                print(f"   {hashtag_name}에서 수집된 공개 게시글이 없습니다.")
                
        except Exception as e:
            print(f"   {hashtag_name} 수집 중 예외 발생: {e}")
            time.sleep(5)
            continue

    print("모든 해시태그 기반 장소/리뷰 채굴이 완료되었습니다!")