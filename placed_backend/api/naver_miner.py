import html
import re
import requests
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from .models import Place, PlaceImage, Review, PlaceAnalysis
from .gemini_service import analyze_review

User = get_user_model()

def get_exact_images_from_naver(keyword, headers, max_count=10):
    url = f"https://openapi.naver.com/v1/search/image.json?query={keyword}&display={max_count}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            return [item.get('link') for item in items if item.get('link')]
    except Exception as e:
        print(f"Image API Error: {e}")
    return []

def mine_from_naver(search_keyword):
    NAVER_CLIENT_ID = "EbTStB1GM_v72tbabUYN"
    NAVER_CLIENT_SECRET = "xf5MVpyvc7"
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    try:
        default_user = User.objects.get(id=1)
    except User.DoesNotExist:
        default_user = User.objects.first()

    if not default_user:
        print("Error: No user found in database.")
        return

    print(f"Starting Multi-Page AI-Analysis Data Pipeline for [{search_keyword}]...")
    
    start_points = [1, 31]
    all_places_items = []
    seen_titles = set() # [핵심 변경] 매장 이름 중복 검사용 바구니
    
    for start_idx in start_points:
        local_url = f"https://openapi.naver.com/v1/search/local.json?query={search_keyword}&display=30&start={start_idx}&sort=comment"
        local_response = requests.get(local_url, headers=headers)
        
        if local_response.status_code == 200:
            items = local_response.json().get("items", [])
            
            for item in items:
                raw_title = item.get("title", "")
                exact_place_name = html.unescape(re.sub(r'<[^>]+>', '', raw_title))
                
                if exact_place_name in seen_titles:
                    continue
                
                seen_titles.add(exact_place_name)
                all_places_items.append(item)
            
    print(f"Total filtered unique places count: {len(all_places_items)}")
    
    for item in all_places_items:
        raw_title = item.get("title", "")
        exact_place_name = html.unescape(re.sub(r'<[^>]+>', '', raw_title))
        exact_address = item.get("roadAddress", item.get("address", "대전광역시 주소 미확인"))
        category_info = item.get('category', '장소')
        
        place, created = Place.objects.get_or_create(
            name=exact_place_name,
            defaults={
                'address': exact_address,
                'description': f"네이버 등록 인증 업체 ({category_info}) 정보입니다."
            }
        )
        
        blog_display_count = 30
        blog_url = f"https://openapi.naver.com/v1/search/blog.json?query={exact_place_name}&display={blog_display_count}"
        blog_response = requests.get(blog_url, headers=headers)
        
        combined_blog_contents = []
        
        if blog_response.status_code == 200:
            blog_data = blog_response.json()
            blog_items = blog_data.get("items", [])
            
            for b_item in blog_items:
                b_title = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("title", "")))
                b_desc = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("description", "")))
                b_link = b_item.get("link", "")
                
                refined_name_short = re.sub(r'(시청점|둔산점|본점|대전둔산점|탄방점|갈마점|유성점|중앙로점)$', '', exact_place_name).strip()
                
                if refined_name_short in b_title or refined_name_short in b_desc:
                    single_review_text = f"[{b_title}] {b_desc}"
                    combined_blog_contents.append(single_review_text)
                    
                    tags = re.findall(r'#[가-힣a-zA-Z0-9_]+', b_desc + b_title)
                    unique_tags = list(set(tags))[:5]
                    if not unique_tags:
                        unique_tags = [f"#{refined_name_short.replace(' ', '')}"]
                    tags_string = ", ".join(unique_tags)
                    
                    try:
                        Review.objects.create(
                            url=b_link,
                            place=place,
                            user=default_user,
                            content=single_review_text,
                            hashtags=tags_string,
                            rating=5
                        )
                    except IntegrityError:
                        continue
        
        final_giant_content = "\n\n".join(combined_blog_contents)
        if not final_giant_content:
            final_giant_content = f"네이버 등록 인증 업체 ({category_info}) 정보입니다."
        
        if created or not place.description:
            place.description = final_giant_content[:1000]
            place.save()
        
        real_images = get_exact_images_from_naver(f"대전 {refined_name_short}", headers, max_count=10)
        for img_url in real_images:
            PlaceImage.objects.get_or_create(
                place=place,
                image_url=img_url
            )

        print(f"   [AI] Analyzing trustworthiness for [{exact_place_name}]...")
        ai_result = analyze_review(final_giant_content)
        trust_score = ai_result.get("non_ad_probability", 50)
        
        PlaceAnalysis.objects.update_or_create(
            name=exact_place_name,
            defaults={
                'content_text': final_giant_content[:2000],
                'is_ad': ai_result.get('is_ad', False),
                'ad_probability': trust_score, 
                'ai_summary': ai_result.get('reason', '분석 완료')
            }
        )
        print(f"   [DB Saved] PlaceAnalysis 등록 완료 -> 신뢰도: {trust_score}%")
        
    print("Success: Finished multi-page data mining pipeline with de-duplication.")