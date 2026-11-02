import json
import re
import google.generativeai as genai
from django.conf import settings

def analyze_review(text, place_name=None):
    """
    settings.py(.env)에 정의된 GEMINI_API_KEY / GEMINI_MODEL_NAME을 사용하여 광고 여부 분석

    [버그 수정] 기존에는 실제 API 키 대신 "**제미나이API키세팅**" 이라는 플레이스홀더
    문자열이 하드코딩되어 있어, generate_response()와 달리 이 함수는 호출될 때마다
    Gemini 인증에 실패하고 except 블록의 기본값(non_ad_probability=50)만 반환하고
    있었습니다. settings.GEMINI_API_KEY(.env 기반)를 사용하도록 통일했습니다.

    [오탐 매칭 완화 2단계 - 장소 관련 정보 유무 판단] place_name을 넘기면, 광고 여부와
    같은 호출 안에서 "이 글이 실제로 이 장소에 대한 알맹이 있는 내용을 담고 있는지"도
    함께 판단합니다(추가 Gemini 호출 없이 프롬프트만 확장 - 비용 증가 없음). 장소명이
    스치듯 한 번 언급되고 끝나는 글, 여러 장소를 나열만 하는 목록형 글 등은
    has_place_info=False로 판정됩니다. place_name을 넘기지 않으면 이 판단 자체를 하지
    않고 항상 True를 반환합니다(호출부에서 필터링에 사용하지 않겠다는 뜻으로 해석).
    """
    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY가 설정되지 않았습니다. 프로젝트 루트의 .env 파일에 "
                "GEMINI_API_KEY=발급받은키 형태로 설정해주세요."
            )
        genai.configure(api_key=api_key)

        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        model = genai.GenerativeModel(model_name)

        place_relevance_instruction = ""
        place_relevance_field = '"has_place_info": true,'
        if place_name:
            place_relevance_instruction = f"""
        [장소 관련 정보 유무 판단 기준]
        가장 중요한 원칙: "{place_name}"라는 이름이 글에 등장한다는 사실 자체는 아무 의미가
        없습니다. 오직 "{place_name}"을(를) 실제로 경험하고 설명하는 문장이 이 글의 핵심
        내용 중 하나인지만 보세요. 장소명이 몇 번 나오든, 그 장소에 대한 구체적인 정보
        (방문 경험, 메뉴/음식, 분위기, 가격, 서비스 등)가 없다면 has_place_info는 false입니다.
        아래와 같은 경우는 특히 false로 판단하세요:
        - 장소명이 스치듯 한 번 언급되고 그 장소에 대한 실제 내용은 없는 경우
          (예: "{place_name} 앞을 지나가는데", "{place_name} 갔었는데 사진을 못 찍었어요")
        - 여러 장소를 나열만 하는 목록형 글이라 "{place_name}"만의 구체적인 설명이 없는 경우
        - 아직 방문하지 않고 여행/방문 일정을 짜거나 남에게 일정을 문의하는 글에서,
          "{place_name}"이 방문 예정 후보 중 하나로만 스쳐 지나가고 그 장소 자체에 대한
          설명이나 경험은 없는 경우 (예: "환승 시간에 {place_name}에서 초밥만 먹고
          공항 가려고요" 처럼 글의 실제 주제는 항공권/일정/다른 관광지이고 이 장소는
          할 일 목록의 한 항목으로만 등장하는 경우)
        - 글 전체 주제가 다른 것(교통편 문의, 다른 지역 여행 코스, 타 장소 추천 요청 등)
          이고 "{place_name}" 언급은 그중 한 문장/한 단어에 그치는 경우

        [게시글 성격 판단 기준 - 리뷰가 아닌 글 탐지]
        이 글이 "그 장소에 대한 실제 방문/이용 후기"가 아니라 다른 성격의 글이면 리뷰로 쓸 수
        없습니다. has_place_info(장소에 대한 구체적 정보가 있는지)와는 별개의 기준입니다 -
        구인공고도 주소나 영업시간 같은 구체적인 정보를 담을 수 있지만, 그래도 리뷰는 아닙니다.
        아래 중 하나에 해당하면 is_review를 false로 판단하세요:
        1. 구인공고/채용 관련 글: 직원·매니저·알바 모집, 급여/근무조건/면접 안내 등
           (반드시 "구인", "채용" 같은 단어가 있어야 하는 건 아닙니다. "함께 일하실 분을 찾아요",
           "정직원으로 모십니다"처럼 다르게 표현된 경우도 포함합니다.)
        2. "{place_name}"과(와) 전혀 무관한 글: 장소명이 다른 의미의 일반 단어/어미와 우연히
           겹쳐서 매칭됐거나, 글의 실제 주제가 이 장소와 아무 상관이 없는 경우
        3. 그 외 리뷰가 아닌 상업적 공고/모집글: 분양, 임대, 체험단/서포터즈 모집, 이벤트 참여
           안내 등
        위 어디에도 해당하지 않고 실제 방문/이용 경험을 다루는 글이면 is_review는 true입니다.
        """
            place_relevance_field = (
                '"has_place_info": true 또는 false '
                f'(위 [장소 관련 정보 유무 판단 기준]에 따라 "{place_name}"에 대한 실질적인 '
                '정보가 있으면 true, 이름만 스치듯 언급되면 false),\n'
                '            "info_reason": "장소 정보가 있다/없다고 판단한 이유를 한 줄로 요약",\n'
                '            "is_review": true 또는 false,\n'
                '            "exclude_reason": is_review가 false일 때만 "job_posting" / "unrelated" / '
                '"other_notice" 중 하나, is_review가 true면 null'
            )

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
        {place_relevance_instruction}
        [분석할 텍스트]
        {text}

        [출력 형식]
        분석 결과는 반드시 아래 형식을 지킨 완벽한 JSON 데이터 구조로만 출력해라.
        특히 'non_ad_probability'는 이 리뷰가 광고가 '아닐' 확률(내돈내산일 확률)을 뜻한다.
        텍스트 외에 앞뒤로 잡담이나 마크다운 기호는 절대 넣지 마라.

        {{
            "is_ad": true 또는 false (광고라고 판단되면 true, 진짜 후기면 false),
            "non_ad_probability": 0부터 100 사이의 정수 (광고가 '아닐' 확률, 즉 순수 후기일 확률),
            "reason": "광고로 판단한 이유 또는 실제 후기로 판단한 이유를 한 줄로 요약",
            {place_relevance_field}
        }}
        """

        response = model.generate_content(prompt)

        # AI가 뱉은 문자열에서 마크다운 및 불필요한 공백 제거
        result_text = response.text.replace('```json', '').replace('```', '').strip()

        # 간혹 AI가 응답 앞뒤에 괄호 외에 딴소리를 적을 때를 대비해 진짜 JSON({ }) 구역만 솎아내는 안전장치
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group()

        result = json.loads(result_text)
        # 안전 기본값: has_place_info가 응답에서 누락돼도 무리하게 걸러내지 않습니다.
        result.setdefault('has_place_info', True)
        # is_review도 누락되면 걸러내지 않고, 목록 밖의 제외 사유는 other_notice로 통일합니다.
        result['is_review'] = result.get('is_review') is not False
        if result['is_review']:
            result['exclude_reason'] = None
        elif result.get('exclude_reason') not in ('job_posting', 'unrelated', 'other_notice'):
            result['exclude_reason'] = 'other_notice'
        return result

    except Exception as e:
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'unknown')
        print(f"Gemini Error ({model_name}): {e}")
        # 에러 발생 시 방어용 안전 기본값 반환 (광고 아닐 확률을 50% 반반으로 처리,
        # 장소 정보 유무는 판단 실패로 무리하게 걸러내지 않도록 True)
        # analysis_failed는 진짜 판정 50%와 구분해 다음 수집 때 재분석하기 위한 표시이고,
        # credits_depleted는 크레딧이 채워질 때까지 모든 호출이 실패한다는 뜻입니다.
        return {
            "is_ad": False, "non_ad_probability": 50,
            "reason": "AI 연동 오류로 인한 분석 실패", "has_place_info": True,
            "is_review": True, "exclude_reason": None,
            "analysis_failed": True,
            "credits_depleted": "credits are depleted" in str(e),
        }


def extract_mood_keywords(place_name, combined_content, allowed_keywords):
    """
    [키워드 기반 장소 구분] 상호명이나 임의의 단어가 섞이지 않도록, allowed_keywords
    (api/keyword_taxonomy.MOOD_KEYWORDS) 목록 중에서만 이 장소에 어울리는 분위기/특징
    키워드를 고르게 합니다. 목록에 없는 값이 응답에 섞여 와도 호출부
    (api/naver_miner.py의 _extract_mood_keywords)에서 한 번 더 걸러내므로, 여기서는
    "고르게 유도"하는 역할만 합니다.

    반환값: 문자열 리스트 (실패 시 빈 리스트 - 안전 기본값. 무리해서 아무거나 채우지 않습니다).
    """
    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY가 설정되지 않았습니다. 프로젝트 루트의 .env 파일에 "
                "GEMINI_API_KEY=발급받은키 형태로 설정해주세요."
            )
        genai.configure(api_key=api_key)

        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-1.5-flash')
        model = genai.GenerativeModel(model_name)

        keyword_list = ", ".join(allowed_keywords)
        prompt = f"""
        당신은 장소 후기를 읽고 분위기/특징 키워드를 골라주는 분류기입니다.

        아래 [후보 키워드 목록]에 있는 단어 중에서만, "{place_name}"이라는 장소와 실제로
        어울리는 것을 최대 5개까지 고르세요.

        [규칙]
        1. 후보 목록에 없는 단어는 절대 새로 만들어내지 마세요.
        2. 상호명, 메뉴 이름, 후보 목록에 없는 형용사는 사용하지 마세요.
        3. 후기 내용만으로 판단이 애매하면 무리해서 고르지 말고 제외하세요.
        4. 어울리는 게 하나도 없으면 빈 배열을 반환하세요.

        [후보 키워드 목록]
        {keyword_list}

        [분석할 후기 모음]
        {combined_content[:4000]}

        [출력 형식]
        아래 형식의 완벽한 JSON 데이터로만 출력하세요. 잡담이나 마크다운 기호는 절대 넣지 마세요.
        {{"keywords": ["후보 목록 중에서 고른 단어", "..."]}}
        """

        response = model.generate_content(prompt)

        result_text = response.text.replace('```json', '').replace('```', '').strip()
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group()

        parsed = json.loads(result_text)
        keywords = parsed.get('keywords', [])
        if not isinstance(keywords, list):
            return []
        return [str(k).strip() for k in keywords if str(k).strip()]

    except Exception as e:
        model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'unknown')
        print(f"Gemini Error ({model_name}): {e}")
        return []


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