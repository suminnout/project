import openai
import json
import datetime

def search_realtime_news(user_question: str) -> list:
    """
    사용자의 질문을 받아 Perplexity API로 실시간 웹 검색을 수행하고,
    관련 뉴스 기사 목록을 반환합니다.
    """

    try:
        client = openai.OpenAI(
            api_key="pplx-XXXXXXXXXXXXXXXX",
            base_url="https://api.perplexity.ai"
        )

        current_date_str = datetime.datetime.now().strftime('%Y년 %m월 %d일')

        prompt = f"""
        # [역할 및 목표 정의]
        당신은 대한민국 K리그의 정책, 운영, 상벌 규정에 대해 깊이 있는 분석을 제공하는 'K리그 전문 뉴스 분석가'입니다. 당신의 목표는 단순 사실 전달을 넘어, 사용자의 질문 의도에 맞는 심층적인 분석이나 평가가 담긴 기사를 찾아내는 것입니다.

        # [컨텍스트 주입]
        - 현재 날짜는 {current_date_str}입니다. '최신'의 기준을 이 날짜로부터 3년 이내로 설정해 주세요.

        # [작업 수행 지침 (단계별 사고 유도 - Chain of Thought)]
        1. 아래 '사용자 질문'의 핵심 의도를 파악하세요.
        2. 해당 의도와 가장 관련성이 높은 뉴스 기사를 검색하되, 다음 '결과물 품질 기준'을 반드시 준수하세요.
        3. 최종적으로 찾은 상위 5개의 기사 정보를 아래 '출력 포맷'에 맞춰 JSON 배열로만 반환하세요.

        # [결과물 품질 기준]
        - 선호 출처: 주요 언론사, 축구 전문 매체의 기사를 최우선으로 고려하세요.
        - 선호 내용: 단순 경기 결과나 선수 동정 기사는 제외하고, '정책 분석', '제도 평가', '칼럼', '심층 취재' 기사를 선호합니다.
        - 제외 대상: 개인 블로그, 커뮤니티 게시글, 광고성 기사는 신뢰도가 낮으므로 결과에서 반드시 제외하세요.
        - 중복 제거: 내용이 거의 동일한 기사는 하나만 선택하세요.

        # [사용자 질문]
        "{user_question}"

        # [출력 포맷]
        - 반드시 아래와 같은 순수한 JSON 배열 형식으로만 응답해야 합니다.
        - 다른 어떤 설명이나 인사말도 포함해서는 안 됩니다.
        - 조건에 맞는 기사를 찾지 못했다면, 빈 배열 `[]`을 반환하세요.
        - 예시:
          [
            {{
              "title": "기사 제목",
              "url": "기사 전체 URL",
              "contents": "기사의 핵심 내용을 2-3문장으로 요약"
            }}
          ]
        """

        # ▼▼▼ 오타 수정된 부분 ▼▼▼
        response = client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": prompt}],
        )

        response_content = response.choices[0].message.content
        news_articles = json.loads(response_content)
        
        return news_articles

    except json.JSONDecodeError:
        print(f"❌ 오류: API가 유효한 JSON을 반환하지 않았습니다. 응답: {response_content}")
        return []
    except Exception as e:
        print(f"❌ Perplexity API 요청 중 오류 발생: {e}")
        return []