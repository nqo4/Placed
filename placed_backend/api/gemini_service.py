import json
import re
import google.generativeai as genai
from django.conf import settings

def analyze_review(text):
    """
    settings.py에 정의된 GEMINI_MODEL_NAME을 사용하여 광고 여부 분석
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        model = genai.GenerativeModel(model_name)

        # 주석을 완전히 풀고 프롬프트를 명확하게 다듬었습니다.
        prompt = f"""
        당신은 한국형 SNS(네이버 블로그, 인스타그램)의 고도화된 뒷광고 및 바이럴 마케팅 탐지 전문가입니다.
        제공된 텍스트를 정밀 분석하여 상업적 광고 여부를 판단하세요.

        [광고 판단 기준]
        1. 대가성 문구 포착: "소정의 원고료", "제품을 제공받아", "협찬받아" 등의 공정위 문구가 있다면 무조건 광고입니다.
        2. SNS 바이럴 패턴: 의미 없는 이모티콘 과다 사용, 기계적인 구성, 상호명 무한 반복, 단점 없는 극찬 일색.

        [진짜 방문 후기 판단 기준]
        1. 내돈내산 인증: 영수증 언급, 가격 대비 만족도(비싸다, 돈값 한다 등)에 대한 구체적 언급.
        2. 아쉬운 점 포함: 웨이팅, 불친절, 양 적음 등 솔직한 부정적 피드백이 섞여 있는 경우.
        3. 구체적인 경험: "여자친구와 기념일에 갔는데", "비 오는 날 방문했더니" 등 개인적인 상황과 자연스러운 말투.

        [분석할 텍스트]
        {text}

        [출력 형식]
        분석 결과는 반드시 아래 형식을 지킨 완벽한 JSON 데이터 구조로만 출력해라. 
        특히 'non_ad_probability'는 이 리뷰가 광고가 '아닐' 확률(내돈내산일 확률)을 뜻한다. 
        텍스트 외에 앞뒤로 잡담이나 마크다운 기호는 절대 넣지 마라.

        {{
            "is_ad": true 또는 false (광고라고 판단되면 true, 진짜 후기면 false),
            "non_ad_probability": 0부터 100 사이의 정수 (광고가 '아닐' 확률, 즉 순수 후기일 확률),
            "reason": "광고로 판단한 이유 또는 실제 후기로 판단한 이유를 한 줄로 요약"
        }}
        """
        
        response = model.generate_content(prompt)
        
        # AI가 뱉은 문자열에서 마크다운 및 불필요한 공백 제거
        result_text = response.text.replace('```json', '').replace('```', '').strip()
        
        # 간혹 AI가 응답 앞뒤에 괄호 외에 딴소리를 적을 때를 대비해 진짜 JSON({ }) 구역만 솎아내는 안전장치
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group()
            
        return json.loads(result_text)
        
    except Exception as e:
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'unknown')
        print(f"Gemini Error ({model_name}): {e}")
        # 에러 발생 시 방어용 안전 기본값 반환 (광고 아닐 확률을 50% 반반으로 처리)
        return {"is_ad": False, "non_ad_probability": 50, "reason": "AI 연동 오류로 인한 분석 실패"}

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
        다음 과정은 내부적으로만 수행하고, 결과에는 절대 포함하지 마십시오.
        1. 정보 수집: 네이버 블로그, 구글 검색 등에서 맛집 및 장소 정보 수집
        2. 지역 필터링: 질문에 언급된 지역을 벗어난 장소는 절대 수집 금지
        3. 검증: 폐업했거나 지도에 없는 가상의 장소는 즉시 제외
        4. 최종 선정: 검증을 통과한 장소만 엄선

        [출력 형식]
        위의 수행 과정이나 잡담을 절대 출력하지 말고, 오직 최종 선정된 장소 목록만 아래 형식으로 출력하십시오.
        
        번호. 상호명
        - 주소: (정확한 도로명 주소)
        - 평가: (맛, 분위기, 서비스 등에 대한 구체적인 평가를 세 문장 이내로 요약)

        [질문]
        {query}
        
        [주의사항]
        - 출력에 사용자 질문이나 프롬프트 내용을 포함하지 마십시오.
        - 별표(*)나 볼드체 마크다운을 절대 사용하지 마십시오.
        - 상호명은 정확해야 하며, 가상의 장소를 창조하지 마십시오.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"Gemini Search Error: {e}")
        return "죄송합니다. 현재 AI 응답을 생성할 수 없습니다."