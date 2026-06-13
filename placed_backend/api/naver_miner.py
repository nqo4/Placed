import html
import re
import requests
from django.contrib.auth import get_user_model
from .models import Place, PlaceImage, Review, PlaceAnalysis
from .gemini_service import analyze_review

User = get_user_model()

def get_exact_images_from_naver(keyword, headers, max_count=5):
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

    print(f"Starting Auto AI-Analysis Data Pipeline for [{search_keyword}]...")
    
    display_count = 15
    local_url = f"https://openapi.naver.com/v1/search/local.json?query={search_keyword}&display={display_count}"
    
    local_response = requests.get(local_url, headers=headers)
    
    if local_response.status_code == 200:
        local_data = local_response.json()
        places_items = local_data.get("items", [])
        
        for item in places_items:
            raw_title = item.get("title", "")
            exact_place_name = html.unescape(re.sub(r'<[^>]+>', '', raw_title))
            exact_address = item.get("roadAddress", item.get("address", "대전광역시 주소 미확인"))
            category_info = item.get('category', '장소')
            
            blog_display_count = 30
            blog_url = f"https://openapi.naver.com/v1/search/blog.json?query={exact_place_name}&display={blog_display_count}"
            blog_response = requests.get(blog_url, headers=headers)
            
            combined_blog_contents = []
            all_extracted_tags = []
            
            if blog_response.status_code == 200:
                blog_data = blog_response.json()
                blog_items = blog_data.get("items", [])
                
                for b_item in blog_items:
                    b_title = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("title", "")))
                    b_desc = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("description", "")))
                    
                    refined_name_short = re.sub(r'(시청점|둔산점|본점|대전둔산점|탄방점|갈마점|유성점|중앙로점)$', '', exact_place_name).strip()
                    
                    if refined_name_short in b_title or refined_name_short in b_desc:
                        combined_blog_contents.append(f"[{b_title}] {b_desc}")
                        tags = re.findall(r'#[가-힣a-zA-Z0-9_]+', b_desc + b_title)
                        all_extracted_tags.extend(tags)
            
            final_giant_content = "\n\n".join(combined_blog_contents)
            
            if not final_giant_content:
                final_giant_content = f"네이버 등록 인증 업체 ({category_info}) 정보입니다."
            
            unique_tags = list(set(all_extracted_tags))[:5]
            if not unique_tags:
                unique_tags = [f"#{refined_name_short.replace(' ', '')}", "#상권분석"]
            tags_string = ", ".join(unique_tags)
            
            place, created = Place.objects.get_or_create(
                name=exact_place_name,
                defaults={
                    'address': exact_address,
                    'description': final_giant_content[:1000]
                }
            )
            
            if not created:
                place.description = final_giant_content[:1000]
                place.save()
            
            real_images = get_exact_images_from_naver(f"대전 {refined_name_short}", headers, max_count=5)
            
            for img_url in real_images:
                PlaceImage.objects.get_or_create(
                    place=place,
                    image_url=img_url
                )
            
            Review.objects.create(
                place=place,
                user=default_user,
                content=final_giant_content,
                hashtags=tags_string,
                rating=5
            )

            print(f"   [AI] Analyzing ad probability for [{exact_place_name}]...")
            ai_result = analyze_review(final_giant_content)
            
            non_ad_percent = ai_result.get("non_ad_probability", 50)
            
            PlaceAnalysis.objects.update_or_create(
                name=exact_place_name,
                defaults={
                    'content_text': final_giant_content[:2000],
                    'is_ad': ai_result.get('is_ad', False),
                    'ad_probability': non_ad_percent, 
                    'ai_summary': ai_result.get('reason', '분석 완료')
                }
            )
            print(f"   [DB Saved] PlaceAnalysis 등록 완료 -> 광고가 아닐 확률: {non_ad_percent}%")
            
        print("Success: Finished high-volume conditional data mining & AI analysis pipeline.")
    else:
        print(f"Local Request failed: {local_response.status_code}")