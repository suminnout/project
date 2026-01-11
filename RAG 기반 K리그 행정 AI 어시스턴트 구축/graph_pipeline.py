from typing import TypedDict, List, Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, END
from search_answer import (
    normalize_query_for_stage1, stage1_retrieve, fetch_candidates_by_ids, rerank_with_late_fusion,
    refine_near_vector_fallback, fetch_final_docs_in_order,
    summarize_documents, build_final_prompt_qa, generate_final_answer_text_qa, get_filtered_news_for_docs,
    INDEX_CLASS, NEAR_CERTAINTY, TOPK_STAGE1, TOPK_FINAL,
    LATE_FUSION_ALPHA, LOW_CONF_FALLBACK
)
from case_search import get_creative_solutions, build_final_prompt_case, generate_final_answer_text_case
from assistant_answer import build_final_prompt_assistant, generate_final_answer_text_assistant

# ──────────────────────────────────────────────────────────────────────────────
# 주제 라우팅 설정 (필요시 클래스명 교체)
# ──────────────────────────────────────────────────────────────────────────────
TOPIC_CONFIG: Dict[str, Dict[str, str]] = {
    "k_league": {
        "index_class": "K_league",  # 실제 Weaviate 클래스명으로 교체
        "system_hint": "당신은 K리그 운영 규정 전문가입니다. 당신은 K리그(한국프로축구연맹) 규정에 특화된 전문 어시스턴트입니다. 사용자의 질문에 대해, 정확하고 간결하며 실무적으로 유용한 K리그 규정 상담을 제공하세요."
    },
    "association": {
        "index_class": "Association",      # 실제 클래스명으로 교체
        "system_hint": "당신은 대한축구협회 규정/지침 전문가입니다. 심판/등록/제재 관련 질문에 조항과 함께 답하세요."
    },
    "international": {
        "index_class": "International", # 실제 클래스명으로 교체
        "system_hint": "당신은 AFC/FIFA 대회 규정 전문가입니다. 공식 규정과 절차를 근거로 명확히 답하세요."
    },
    "team": {
        "index_class": "Team",  # 실제 클래스명으로 교체
        "system_hint": "당신은 구단 운영/선수 계약/이적 절차 전문가입니다. 단계별로 실무 지침을 제시하세요."
    },
}

DEFAULT_CONFIG: Dict[str, str] = {
    "index_class": INDEX_CLASS,  # 기존 기본값
    "system_hint": "당신은 축구 규정 어시스턴트입니다. 관련 규정과 절차를 근거와 함께 한국어로 답하세요."
}

# ──────────────────────────────────────────────────────────────────────────────
# 상태 정의
# ──────────────────────────────────────────────────────────────────────────────
class State(TypedDict, total=False):
    user_query: str
    big_topic: Literal["qa", "cases", "assistant"]
    sub_topic: Optional[str]
    mode: Literal["qa", "cases", "assistant"]

    index_class: str
    system_hint: str

    history_summary: str

    # 주제 1
    query_vec: Any
    ids_stage1: List[Any]
    id_list: List[str]
    cands: List[Dict[str, Any]]
    top_ids: List[str]
    top_score: float
    docs: List[Dict[str, Any]]
    summaries: List[str]
    summary_block: str
    filtered_news: List[Dict[str, Any]]
    news_block: str
    final_answer: str

    # 주제 2
    case_solutions: List[Dict[str, Any]]

    result: Dict[str, Any]

# ──────────────────────────────────────────────────────────────────────────────
# 노드 정의
# ──────────────────────────────────────────────────────────────────────────────
def node_init(s: State) -> State:
    # 1) 모드 라우팅
    mode = s.get('big_topic', "qa")
    s['mode'] = mode

    # 2) QA일 때만 소주제로 인덱스/힌트 결정
    if (mode == "qa"):
        t = (s.get("sub_topic") or "k_league").strip()
        cfg = TOPIC_CONFIG.get(t, DEFAULT_CONFIG)
        s["index_class"] = cfg["index_class"]
        s["system_hint"] = cfg["system_hint"]
    return s

def route_mode(s: State) -> str:
    return s.get("mode", "qa")

def node_router(s: State) -> State:
    return s

# ── QA(Q/A) 플로우 ────────────────────────────────────────────────────
def node_pretranslate(s: State) -> State:
    try:
        uq = s["user_query"]
        ix = s["index_class"]
        new_q = normalize_query_for_stage1(uq, index_class=ix)
        s["user_query"] = new_q
    except Exception:
        # 번역 실패 시 원문 유지 (안전 폴백)
        pass
    return s

def node_stage1(s: State) -> State:
    qv, ids, id_list = stage1_retrieve(
        s["user_query"],
        index_class=s["index_class"], near_certainty=NEAR_CERTAINTY, topk=TOPK_STAGE1
    )
    s.update({"query_vec": qv, "ids_stage1": ids, "id_list": id_list})
    return s

def node_fetch(s: State) -> State:
    s["cands"] = fetch_candidates_by_ids(s["id_list"], index_class=s["index_class"])
    return s

def node_rerank(s: State) -> State:
    top_ids, top_score = rerank_with_late_fusion(
        s["query_vec"], s["ids_stage1"], s["cands"],
        alpha=LATE_FUSION_ALPHA, topk=TOPK_FINAL
    )
    s.update({"top_ids": top_ids, "top_score": top_score})
    return s

def need_fallback(s: State) -> bool:
    return (not s.get("top_ids")) or (s.get("top_score", 0.0) < LOW_CONF_FALLBACK)

def node_fallback(s: State) -> State:
    s["docs"] = refine_near_vector_fallback(
        s["id_list"], s["query_vec"],
        index_class=s["index_class"], near_certainty=NEAR_CERTAINTY, topk=TOPK_FINAL
    )
    return s

def node_finalfetch(s: State) -> State:
    s["docs"] = fetch_final_docs_in_order(s["top_ids"], index_class=s["index_class"])
    return s

def node_newsfilter(s: State) -> State:
    filtered_news, _sim, news_block = get_filtered_news_for_docs(
        s["user_query"], s["docs"], max_keep=5
    )
    s.update({
        "filtered_news": filtered_news,
        "news_block": news_block,
        # "news_sim": _sim,  # 필요 시 주석 해제
    })
    return s

def node_summarize(s: State) -> State:
    summaries, sb = summarize_documents(s["docs"])
    s.update({"summaries": summaries, "summary_block": sb})
    return s

def node_final_answer_qa(s: State) -> State:
    prompt = build_final_prompt_qa(
        s["user_query"], s["summary_block"],
        system_hint=s.get("system_hint"),
        news_block=s.get("news_block", ""),
        history_summary=s.get("history_summary", "")
    )
    s["final_answer"] = generate_final_answer_text_qa(prompt)
    return s

def node_pack_qa(s: State) -> State:
    # 1) 문서 컨텍스트
    doc_contexts = [
        {
            "span_id": (d.get("_additional") or {}).get("id", ""),
            "text": (d.get("content") or d.get("table_json") or "").strip()
        }
        for d in s.get("docs", []) if (d.get("content") or d.get("table_json"))
    ]

    # 2) 뉴스 컨텍스트 (지금은 news_block이 문자열이므로 블록 전체를 1개 컨텍스트로 추가)
    news_block = (s.get("news_block") or "").strip()
    news_contexts = []
    if news_block:
        news_contexts = [{"span_id": "NEWS_BLOCK", "text": news_block}]

    # 3) 평가용: 합친 컨텍스트 제공
    all_contexts = doc_contexts + news_contexts

    s["result"] = {
        "mode": "qa",
        "final_answer": s["final_answer"],
        "contexts": doc_contexts,          # 기존 필드 유지 (문서만)
        "news_block": news_block,          # 뉴스 원문 블록 추가
        "all_contexts": all_contexts,      # ★ 평가용으로 합친 컨텍스트
        "index_class": s.get("index_class"),
        "top_score": s.get("top_score"),
        "sub_topic": s.get("sub_topic")
    }
    return s

# ── CASE(사례 탐색) 플로우 ────────────────────────────────────────────────────
def node_case_generate(s: State) -> State:
    try:
        solutions = get_creative_solutions(s["user_query"])
    except Exception:
        solutions = []
    s["case_solutions"] = solutions
    return s

def node_final_answer_case(s: State) -> State:
    prompt = build_final_prompt_case(
        s["user_query"], s['case_solutions'], history_summary=s.get("history_summary", "")
    )
    s["final_answer"] = generate_final_answer_text_case(prompt)
    return s

def node_pack_case(s: State) -> State:
    s["result"] = {
        "mode": "case",
        "query": s.get("user_query", ""),
        "final_answer": s.get("final_answer", ""),
        "all_contexts": s.get("case_solutions"),
    }
    return s

# ── ASSISTANT(업무 보조) 플로우 ────────────────────────────────────────────────────
def node_final_answer_assistant(s: State) -> State:
    prompt = build_final_prompt_assistant(
        s["user_query"], history_summary=s.get("history_summary", "")
    )
    s["final_answer"] = generate_final_answer_text_assistant(prompt)
    return s

def node_pack_assistant(s: State) -> State:
    s["result"] = {
        "mode": "assistant",
        "query": s.get("user_query", ""),
        "final_answer": s.get("final_answer", ""),
    }
    return s

# ──────────────────────────────────────────────────────────────────────────────
# 그래프 구성
# ──────────────────────────────────────────────────────────────────────────────
graph = StateGraph(State)
graph.add_node("init", node_init)
graph.add_node("router", node_router)

# 주제 1
graph.add_node("pretranslate", node_pretranslate)
graph.add_node("stage1", node_stage1)
graph.add_node("fetch", node_fetch)
graph.add_node("rerank", node_rerank)
graph.add_node("fallback", node_fallback)
graph.add_node("finalfetch", node_finalfetch)
graph.add_node("summarize", node_summarize)
graph.add_node("newsfilter", node_newsfilter)
graph.add_node("final_answer", node_final_answer_qa)
graph.add_node("pack", node_pack_qa)

# 주제 2
graph.add_node("case_generate", node_case_generate)
graph.add_node("final_answer_case", node_final_answer_case)
graph.add_node("pack_case", node_pack_case)

# 주제 3
graph.add_node("final_answer_assistant", node_final_answer_assistant)
graph.add_node("pack_assistant", node_pack_assistant)

# Entry
graph.set_entry_point("init")
graph.add_conditional_edges(
    "init",
    route_mode,
    {"qa": "pretranslate",
     "cases": "case_generate",
     "assistant": "final_answer_assistant"}
)

# 주제 1
graph.add_edge("pretranslate", "stage1")
graph.add_edge("stage1", "fetch")
graph.add_edge("fetch", "rerank")
graph.add_conditional_edges("rerank", need_fallback, {True: "fallback", False: "finalfetch"})
graph.add_edge("fallback", "summarize")
graph.add_edge("finalfetch", "summarize")
graph.add_edge("summarize", "newsfilter")
graph.add_edge("newsfilter", "final_answer")
graph.add_edge("final_answer", "pack")
graph.add_edge("pack", END)

# 주제 2
graph.add_edge("case_generate", "final_answer_case")
graph.add_edge("final_answer_case", "pack_case")
graph.add_edge("pack_case", END)

# 주제 3
graph.add_edge("final_answer_assistant", "pack_assistant")
graph.add_edge("pack_assistant", END)

app = graph.compile()

# ──────────────────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────────────────

def graph_generate_answer(user_query: str, big_topic: Literal["qa", "cases", "assistant"], sub_topic: Optional[str] = None, history_summary: str = ""):
    s = app.invoke({"user_query": user_query, "big_topic": big_topic, "sub_topic": sub_topic, "history_summary": history_summary})
    return s["result"]
