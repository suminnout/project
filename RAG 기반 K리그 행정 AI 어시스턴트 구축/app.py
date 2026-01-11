from flask import Flask, request, render_template, jsonify
from graph_pipeline import graph_generate_answer as generate_answer

from collections import defaultdict, deque
from mcp_notion_sink import save_answer_to_notion

HISTORY_MAX = 8

# 두 레벨로 저장: (1) big_topic 전용, (2) big_topic+sub_topic 전용
history_all = deque(maxlen=HISTORY_MAX)

def push_turn(role: str, text: str):
    history_all.append(f"[{role}] {text}")

def build_history_block(limit: int | None = None) -> str:
    return "\n".join(list(history_all)[-(limit or HISTORY_MAX):])
  
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    # POST 요청에서 사용자 메시지 받기
    user_message = request.form.get('message', '').strip()
    big_topic    = (request.form.get('big_topic') or 'qa').strip().lower()   # 'qa' | 'cases' | 'assistant'
    sub_topic    = (request.form.get('topic') or '').strip().lower()
    
    # 2) Q/A가 아니면 소주제는 무시
    if (big_topic != 'qa'):
        sub_topic = None

    if not user_message:
        return jsonify({'error': '메시지를 입력해주세요.'})

    # (A) 이 턴에서 사용할 히스토리 블록 생성
    history_block = build_history_block()

    # (B) 그래프 실행: history_summary 추가된 새 시그니처 사용
    ai_response = generate_answer(
        user_message, big_topic, sub_topic, history_summary=history_block
    )

    # (C) 이번 턴을 요약해 저장 (사용자/AI 각각)
    push_turn("U", user_message)
    push_turn("A", ai_response["final_answer"])

    notion_title = f"[{big_topic}/{sub_topic}] {user_message}"
    notion_meta = {"big_topic": big_topic, "sub_topic": sub_topic}
    
    if (big_topic == 'qa'):
        # 면책 조항 추가
        if (sub_topic == 'k_league'):
            disclaimer = "\n\n ⚠️ 정식 규정 PDF는 한국프로축구연맹(K리그) 홈페이지에서도 확인하실 수 있습니다. \n ⚽ [K리그 홈페이지](https://www.kleague.com/about/regulations.do)"
        elif (sub_topic == 'association'):
            disclaimer = "\n\n ⚠️ 정식 규정 PDF는 대한축구협회 홈페이지에서도 확인하실 수 있습니다. \n 🏛️ [대한축구협회 홈페이지](https://www.kfa.or.kr/kfa/data_room.php?act=rule)"
        elif (sub_topic == 'international'):
            disclaimer = "\n\n ⚠️ 정식 규정 PDF는 아시아축구연맹(AFC) 홈페이지에서도 확인하실 수 있습니다. \n 🌍 [AFC 홈페이지](https://www.the-afc.com/en/more/downloads.html?utm_source=chatgpt.com)"
        elif (sub_topic == 'team'):
            disclaimer = "\n\n ⚠️ 자세한 내용은 강원FC에 문의하세요. \n 🏟️ [강원FC 홈페이지](https://www.gangwon-fc.com/)"
    
        final_text = ai_response["final_answer"] + disclaimer
        info = None
        try:
            info = save_answer_to_notion(notion_title, ai_response["final_answer"], notion_meta)
            print("NotionSave debug:", info)  # 콘솔에 무조건 찍힘
            if info and info.get("ok") and info.get("url"):
                notion_link = info["url"]
                final_text += f"\n\n🔗 [Notion]({notion_link})"
            else:
                # 실패/스킵 사유를 로깅
                app.logger.warning("Notion save skipped/failed: %s", info)
        except Exception as e:
            app.logger.exception("Notion 저장 실패(예외): %s", e)

        # 응답 JSON에도 같이 내려주면 프런트에서 바로 확인 가능
        return jsonify({
            "ai_response": final_text,
            "notion_info": info  # ← ok/url/reason/debug 가 들어있음
        })
    
    final_text = ai_response["final_answer"]
    
    info = None
    try:
        info = save_answer_to_notion(notion_title, ai_response["final_answer"], notion_meta)
        print("NotionSave debug:", info)  # 콘솔에 무조건 찍힘
        if info and info.get("ok") and info.get("url"):
            notion_link = info["url"]
            final_text += f"\n\n🔗 [Notion]({notion_link})"
        else:
            # 실패/스킵 사유를 로깅
            app.logger.warning("Notion save skipped/failed: %s", info)
    except Exception as e:
        app.logger.exception("Notion 저장 실패(예외): %s", e)

    # 응답 JSON에도 같이 내려주면 프런트에서 바로 확인 가능
    return jsonify({
        "ai_response": final_text,
        "notion_info": info  # ← ok/url/reason/debug 가 들어있음
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
