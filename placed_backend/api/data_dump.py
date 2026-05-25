import re
from api.models import Place, Review, User

def insert_mock_data():
    try:
        default_user = User.objects.get(id=1)
    except User.DoesNotExist:
        default_user = User.objects.first()

    if not default_user:
        print("오류: 데이터베이스에 등록된 유저가 없습니다.")
        return

    # 대전의 실제 핫플레이스를 기반으로 정교하게 짠 10개의 추가 데이터 리스트
    mock_places_data = [
        {
            "name": "인터뷰 카페", 
            "address": "대전 유성구 한밭대로371번길 25-3",
            "image": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=500",
            "content": "궁동 감성 가득한 인터뷰 카페 다녀왔어요. 초록초록한 뷰가 너무 예쁘고 사진 찍기 딱 좋습니다. 음료는 쏘쏘하지만 분위기 값으로 인정! #대전카페 #궁동카페 #인터뷰카페 #내돈내산"
        },
        {
            "name": "성심당 본점", 
            "address": "대전 중구 종합길 15",
            "image": "https://images.unsplash.com/photo-1608686207856-001b95cf60ca?w=500",
            "content": "📍 대전의 명물 성심당 본점 습격! 튀김소보로랑 명란바게트 샀는데 역시 갓 나온 빵이 진리네요. 줄은 길지만 회전율 빨라서 금방 들어감! #대전맛집 #성심당 #빵지순례"
        },
        {
            "name": "오문창순대국밥", 
            "address": "대전 대덕구 계족로 670",
            "image": "https://images.unsplash.com/photo-1627308595229-7830a5c91f9f?w=500",
            "content": "24시 언제 가도 든든한 오문창순대국밥. 파다대기 팍팍 넣어서 먹으면 전날 마신 술이 확 풀립니다. 가성비 대박이고 냄새 안 나서 초보자도 가능 #대전국밥 #중리동맛집 #내돈내산리뷰"
        },
        {
            "name": "동은성", 
            "address": "대전 중구 대종로 532-1",
            "image": "https://images.unsplash.com/photo-1585032226651-759b368d7246?w=500",
            "content": "[체험단 후기] 대흥동 유명한 냄비짬뽕 맛집 동은성 방문! 낙지랑 조개가 냄비 터지도록 들어가 있어서 국물이 진짜 시원해요. 탕수육도 바삭함 그 자체 #대흥동맛집 #대전짬뽕맛집 #협찬제공"
        },
        {
            "name": "태평소국밥 본점", 
            "address": "대전 유성구 온천동로65번길 50",
            "image": "https://images.unsplash.com/photo-1547058881-aa0edd92aab3?w=500",
            "content": "드디어 영접한 태평소국밥 육사시미와 소국밥 조합. 육사시미는 만원에 이 퀄리티라니 말 안 됨. 국밥도 국물이 맑고 깊어서 밥 한 공기 뚝딱입니다. #유성맛집 #태평소국밥 #대전핫플"
        },
        {
            "name": "카라멜(Karamael)", 
            "address": "대전 중구 보문로262번길 47",
            "image": "https://images.unsplash.com/photo-1612874742237-6526221588e3?w=500",
            "content": "📍 선화동 뇨끼 맛집 카라멜. [소정의 원고료를 지원받아 작성] 인테리어 가구부터 힙한 감성이 넘쳐나요. 생면 파스타라 식감이 쫄깃하고 트러플 뇨끼 풍미가 예술입니다. #선화동맛집 #대전파스타 #광고후기"
        },
        {
            "name": "코너스톤에이치", 
            "address": "대전 유성구 가정로 310-14",
            "image": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=500",
            "content": "신성동 조용한 주택가에 있는 코너스톤에이치. 일본식 드립 커피와 고급스러운 크렘브륄레 디저트가 세트로 나옵니다. 조용히 책 읽기 좋은 공간으로 추천합니다. #신성동카페 #연구단지카페"
        },
        {
            "name": "진로집", 
            "address": "대전 중구 대흥로157번길 42",
            "image": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=500",
            "content": "대전 노포 감성의 정석 진로집 두부두루치기. 중간맛도 제법 매콤해요. 면사리 무조건 추가해서 비벼 드세요! 막걸리를 부르는 중독성 강한 맛입니다. #대전노포 #두부두루치기 #대흥동핫플"
        },
        {
            "name": "탑정호 레이크뷰 카페", 
            "address": "충남 논산시 탑정로 666",
            "image": "https://images.unsplash.com/photo-1507133750040-4a8f57021571?w=500",
            "content": "📍 대전 근교 드라이브 코스로 좋은 탑정호 레이크뷰 대형 카페. [업체로부터 서비스를 제공받았습니다] 통창 너머로 보이는 호수 뷰가 힐링 그 자체예요. 베이커리 종류도 짱 많음 #대전근교카페 #탑정호카페 #체험단광고"
        },
        {
            "name": "정식당", 
            "address": "대전 중구 중앙로130번길 24",
            "image": "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=500",
            "content": "대흥동 골목에 숨겨진 정식당 닭볶음탕! 매콤달콤한 양념이 감자랑 고기에 쏙 배어있어서 볶음밥까지 싹싹 긁어먹고 왔네요. 친구들이랑 가기 딱 좋음 #대흥동정식당 #대전닭볶음탕 #내돈내산맛집"
        }
    ]

    # 기존 데이터와 중복되지 않게 검사하며 저장
    for item in mock_places_data:
        place, created = Place.objects.get_or_create(
            name=item["name"],
            defaults={
                'address': item["address"],
                'image_url': item["image"],
                'description': "인스타그램 스타일 마이닝 데이터"
            }
        )
        
        # 주소와 이미지 동기화
        if not created:
            place.address = item["address"]
            place.image_url = item["image"]
            place.save()

        # 해시태그 추출 알고리즘 (#단어 분리)
        extracted_tags = re.findall(r'#[가-힣a-zA-Z0-9_]+', item["content"])
        tags_string = ", ".join(extracted_tags) if extracted_tags else ""
        
        Review.objects.create(
            place=place,
            user=default_user,
            content=item["content"],
            hashtags=tags_string,
            rating=5
        )
        print(f"적재 완료: [{place.name}] -> 태그: {tags_string}")

    print(f"총 {len(mock_places_data)}개의 대용량 더미 데이터가 DB에 완벽히 저장되었습니다.")