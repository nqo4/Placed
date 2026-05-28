import html
import requests
import re
import html
from api.models import Place, Review, User, PlaceImage
from django.contrib.auth import get_user_model

User  = get_user_model()

def get_exact_images_from_naver(place_name, headers, max_count=3):
    """네이버 이미지 검색 API를 통해 해당 장소의 실제 사진 URL을 안전하게 가져오는 함수"""
    image_url = f"https://openapi.naver.com/v1/search/image?query={place_name}&display={max_count}&sort=sim"
    img_urls = []
    
    try:
        res = requests.get(image_url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            for item in items:
                link = item.get("link", "")
                if link:
                    img_urls.append(link)
    except Exception as e:
        print(f"Error fetching images via API: {e}")
        
    return img_urls

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

    print(f"Starting Bulk Naver Local & Image API for [{search_keyword}]...")
    
    display_count = 50
    
    start_indices = [1, 51]
    
    for start_num in start_indices:
        local_url = f"https://openapi.naver.com/v1/search/local.json?query={search_keyword}&display={display_count}&start={start_num}"
        local_response = requests.get(local_url, headers=headers)
        
        if local_response.status_code == 200:
            local_data = local_response.json()
            places_items = local_data.get("items", [])
            
            if not places_items:
                break
                
            for item in places_items:
                raw_title = item.get("title", "")
                exact_place_name = html.unescape(re.sub(r'<[^>]+>', '', raw_title))
                exact_address = item.get("roadAddress", item.get("address", "대전광역시 주소 미확인"))
                
                category_info = item.get('category', '장소')
                
                blog_url = f"https://openapi.naver.com/v1/search/blog.json?query={exact_place_name}&display=1"
                blog_response = requests.get(blog_url, headers=headers)
                
                initial_description = f"네이버 등록 인증 업체 ({category_info})입니다."
                b_desc = ""
                tags_string = ""
                
                if blog_response.status_code == 200:
                    blog_data = blog_response.json()
                    blog_items = blog_data.get("items", [])
                    
                    for b_item in blog_items:
                        b_title = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("title", "")))
                        b_desc = html.unescape(re.sub(r'<[^>]+>', '', b_item.get("description", "")))
                        
                        if b_desc:
                            initial_description = b_desc[:150]
                        
                        refined_name_for_tag = re.sub(r'(시청점|둔산점|본점|대전둔산점|탄방점|갈마점|유성점|중앙로점)$', '', exact_place_name).strip()
                        extracted_tags = re.findall(r'#[가-힣a-zA-Z0-9_]+', b_desc + b_title)
                        if not extracted_tags:
                            extracted_tags = [f"#{refined_name_for_tag.replace(' ', '')}", "#API수집"]
                        tags_string = ", ".join(extracted_tags)
                
                place, created = Place.objects.get_or_create(
                    name=exact_place_name,
                    defaults={
                        'address': exact_address,
                        'description': initial_description
                    }
                )
                
                if not created:
                    place.description = initial_description
                    place.save()
                
                print(f"Mapped place: [{exact_place_name}]")
                
                refined_name = re.sub(r'(시청점|둔산점|본점|대전둔산점|탄방점|갈마점|유성점|중앙로점)$', '', exact_place_name).strip()
                print(f"   Fetching 5 images via API for [{refined_name}]...")
                
                real_images = get_exact_images_from_naver(f"대전 {refined_name}", headers, max_count=5)
                
                for img_url in real_images:
                    PlaceImage.objects.get_or_create(
                        place=place,
                        image_url=img_url
                    )
                    print(f"      -> Image saved: {img_url[:50]}...")
                
                if b_desc:
                    Review.objects.create(
                        place=place,
                        user=default_user,
                        content=b_desc,
                        hashtags=tags_string,
                        rating=5
                    )
            
            print(f"Success: Mined a page of places for [{search_keyword}].")
        else:
            print(f"Local Request failed with status code: {local_response.status_code}")
            break