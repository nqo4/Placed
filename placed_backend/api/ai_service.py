import google.generativeai as genai
from django.conf import settings
import json

def analyze_review(text):
    """
    settings.py에 정의된 GEMINI_MODEL_NAME을 사용하여 광고 여부 분석
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # 설정된 모델명 가져오기 (없으면 1.5-flash 기본값)
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        model = genai.GenerativeModel(model_name)

        # prompt = f"""
        # 당신은 한국형 SNS(네이버 블로그, 인스타그램, 유튜브)의 **고도화된 뒷광고 및 바이럴 마케팅 탐지 전문가**입니다.
        # 제공된 텍스트를 정밀 분석하여 상업적 광고 여부를 판단하세요.

        # [광고 판단 기준 (아래 패턴이 보이면 광고 확률을 높게 잡으세요)]
        # 1. **대가성 문구 포착**: 
        #    - 텍스트의 처음이나 끝(혹은 중간에 숨겨진) "소정의 원고료", "제품을 제공받아", "서비스를 협찬받아", "업체로부터 지원받아" 등의 공정위 문구가 있는지 확인.
        #    - "솔직하게 작성하였습니다"라고 써있더라도, 물품/서비스를 받았다면 **100% 광고**입니다.
        # 2. **SNS 바이럴 패턴**:
        #    - **이모티콘 과다 사용**: (예: 🌟, ✨, 👍, 📍) 문장 끝마다 반복적인 이모티콘.
        #    - **기계적인 구성**: [위치] -> [인테리어] -> [메뉴] -> [총평] 의 템플릿 같은 구조.
        #    - **키워드 반복**: 검색 노출을 위해 특정 상호명이나 "강남맛집" 같은 단어를 부자연스럽게 반복.
        #    - **과도한 칭찬**: 단점 언급 없이 "완벽하다", "무조건 가야한다", "인생 맛집" 등 극찬 일색.
        # 3. **해시태그 분석**: #맛집 #추천 #핫플 #데이트 등 일반적인 인기 키워드가 본문 내용보다 비대하게 많은 경우.

        # [진짜 방문 후기 판단 기준 (아래 특징이 보이면 **광고가 아님**으로 판단하세요)]
        # 1. **내돈내산 인증**: 영수증 사진 언급, 결제 내역, "비싸지만", "돈 아깝다/안아깝다" 등 지불에 대한 구체적 언급.
        # 2. **단점 및 아쉬운 점 포함**: "웨이팅이 너무 길었다", "직원이 불친절했다", "맛은 있는데 양이 적다" 등 솔직한 부정적 피드백이 섞여 있는 경우.
        # 3. **구체적이고 개인적인 경험**: 단순한 매장 홍보가 아니라, "여자친구와 기념일에 갔는데", "비 오는 날 방문했더니" 등 개인적인 상황(Context)과 감정이 묻어나는 글.
        # 4. **자연스러운 말투**: 맞춤법이 조금 틀리거나, 정제되지 않은 구어체, "ㅋㅋ", "ㅠㅠ" 같은 감정 표현이 자연스럽게 섞인 경우.

        # [분석할 텍스트]
        # {text}

        # 분석 결과는 반드시 아래 JSON 형식으로만 출력해:
        # {{
        #     "is_ad": true/false,
        #     "probability": 0~100 사이의 숫자,
        #     "reason": "광고로 판단한 이유 또는 실제 후기로 판단한 이유를 한 줄로 요약"
        # }}
        
        # 분석할 텍스트:
        # {text}
        # """
        
        response = model.generate_content(prompt)
        
        # JSON 파싱 (마크다운 제거)
        result_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(result_text)
        
    except Exception as e:
        print(f"Gemini Error ({settings.GEMINI_MODEL_NAME}): {e}")
        # 에러 발생 시 기본값 반환
        return {"is_ad": False, "probability": 0, "reason": "AI 분석 실패"}

def generate_response(query):
    """
    일반적인 질문에 대한 Gemini 응답 생성 (광고 필터링 강화)
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        model = genai.GenerativeModel(model_name)

        prompt = f"""
        당신은 빈틈없는 '장소 검증 및 추천 에이전트'입니다.
        사용자의 질문을 분석하여 장소를 추천하십시오.
        
        [수행 지침]
        다음 과정은 **내부적으로만 수행**하고, 결과에는 절대 포함하지 마십시오.
        1. 정보 수집: 네이버 블로그, 구글 검색, 유튜브, 인스타그램 등에서 맛집 및 장소 정보 수집
        2. 지역 필터링: 질문에 언급된 지역(예: '강남')을 벗어난 장소는 절대 수집 금지
        3. 검증: 폐업했거나 지도에 없는 가상의 장소는 즉시 제외
        4. 최종 선정: 검증을 통과한 장소만 엄선

        [출력 형식]
        위의 수행 과정이나 잡담(예: "분석 결과입니다", "1단계...")을 **절대 출력하지 말고**, 
        오직 **최종 선정된 장소 목록**만 아래 형식으로 출력하십시오.
        
        번호. 상호명
        - 주소: (정확한 도로명 주소)
        - 평가: (맛, 분위기, 서비스 등에 대한 구체적인 평가를 세 문장 이내로 요약)

        [질문]
        {query}
        
        [주의사항]
        - **출력에 사용자 질문이나 프롬프트 내용을 포함하지 마십시오.**
        - **(별표)나 볼드체 마크다운을 절대 사용하지 마십시오.**
        - 상호명은 정확해야 하며, 가상의 장소를 창조하지 마십시오.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"Gemini Search Error: {e}")
        return "죄송합니다. 현재 AI 응답을 생성할 수 없습니다."