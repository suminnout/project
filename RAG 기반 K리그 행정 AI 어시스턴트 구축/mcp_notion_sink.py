from __future__ import annotations
import json
import pathlib
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import requests

# ─────────────────────────────────────────────────────────
# 설정 로드(.env 대신 config/mcp.json 사용)
CFG_PATH = pathlib.Path("config/mcp.json")
MCP_CFG = json.loads(CFG_PATH.read_text(encoding="utf-8")) if CFG_PATH.exists() else {}

NOTION_VERSION = "2022-06-28"         # 안정 버전
MAX_CHILDREN_PER_REQUEST = 90         # Notion API: 한 번에 추가 가능한 children 수 여유값
RICH_TEXT_CHUNK = 1800                # 한 rich_text 길이의 안전 분할 크기(내용은 모두 이어 붙여 보냄)

# DB의 title 속성명 캐시
_DB_TITLE_PROP_CACHE: Dict[str, str] = {}
# ─────────────────────────────────────────────────────────


# ============== 유틸 ==============
def _debug_snapshot() -> dict:
    return {
        "has_parent_url": bool(MCP_CFG.get("parent_url")),
        "has_db_url": bool(MCP_CFG.get("db_url")),
        "has_notion_token": bool(MCP_CFG.get("notion_api_token")),
        "save_flag": MCP_CFG.get("save", True),
    }

def _extract_page_id_from_url(u: str) -> Optional[str]:
    """
    Notion URL에서 32자리 hex를 추출해 UUID 하이픈 형식으로 반환.
    예: .../slug-4b090b7fac1a4a7c912b219cbaa0594f → 4b090b7f-ac1a-4a7c-912b-219cbaa0594f
    """
    try:
        path = urlparse(u).path
    except Exception:
        path = u
    s = re.sub(r"[^0-9a-f]", "", path.lower())
    m = re.search(r"([0-9a-f]{32})", s)
    if not m:
        return None
    raw = m.group(1)
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"

def _chunks(lst: List[Any], size: int) -> List[List[Any]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def _chunk_text(s: str, limit: int = RICH_TEXT_CHUNK):
    for i in range(0, len(s), limit):
        yield s[i:i+limit]

def _rich_text(text: str) -> List[Dict[str, Any]]:
    # 긴 텍스트도 여러 조각으로 나눠 하나의 블록에 순서대로 삽입
    return [{"type": "text", "text": {"content": part}} for part in _chunk_text(text)]

# ============== Markdown → Blocks ==============
def _markdown_to_blocks(md: str) -> List[Dict[str, Any]]:
    """
    가벼운 Markdown → Notion blocks 변환:
    - #, ##, ### → heading_1/2/3
    - - / * → bulleted_list_item
    - 1. 2. → numbered_list_item
    - - [ ] / - [x] → to_do
    - ```lang ... ``` → code (길면 여러 code 블록으로 분할)
    - 나머지 → paragraph (길면 여러 paragraph로 분할)
    ※ 내용은 절대 잘라내지 않으며, 길면 '여러 블록'으로 분리하여 모두 넣습니다.
    """
    blocks: List[Dict[str, Any]] = []
    md = md.replace("\r\n", "\n")
    lines = md.split("\n")

    in_code = False
    code_lang = "plain text"
    code_buf: List[str] = []
    para_buf: List[str] = []

    def flush_para():
        nonlocal para_buf
        if not para_buf:
            return
        text = " ".join(para_buf).strip()
        if text:
            for part in _chunk_text(text):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": _rich_text(part)}
                })
        para_buf = []

    def flush_code():
        nonlocal code_buf, code_lang
        if not code_buf:
            return
        text = "\n".join(code_buf)
        # 코드도 길면 여러 code 블록으로 분할
        for part in _chunk_text(text):
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": code_lang,
                    "rich_text": [{"type": "text", "text": {"content": part}}]
                }
            })
        code_buf = []
        code_lang = "plain text"

    for raw in lines:
        line = raw.rstrip("\n")

        # fenced code block 토글
        if line.strip().startswith("```"):
            fence = line.strip()[3:].strip()
            if not in_code:
                flush_para()
                in_code = True
                code_lang = fence or "plain text"
                code_buf = []
            else:
                flush_code()
                in_code = False
            continue

        if in_code:
            code_buf.append(line)
            continue

        # 헤딩
        if line.startswith("### "):
            flush_para()
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": _rich_text(line[4:])}})
            continue
        if line.startswith("## "):
            flush_para()
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": _rich_text(line[3:])}})
            continue
        if line.startswith("# "):
            flush_para()
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": _rich_text(line[2:])}})
            continue

        stripped = line.strip()

        # 체크리스트
        if stripped.startswith(("- [ ] ", "* [ ] ")):
            flush_para()
            text = stripped[6:]
            # 길면 to_do 여러개로 분할
            for part in _chunk_text(text):
                blocks.append({"object": "block", "type": "to_do",
                               "to_do": {"checked": False, "rich_text": _rich_text(part)}})
            continue
        if stripped.startswith(("- [x] ", "* [x] ", "- [X] ", "* [X] ")):
            flush_para()
            text = stripped[6:]
            for part in _chunk_text(text):
                blocks.append({"object": "block", "type": "to_do",
                               "to_do": {"checked": True, "rich_text": _rich_text(part)}})
            continue

        # 리스트
        if stripped.startswith(("- ", "* ")):
            flush_para()
            text = stripped[2:]
            for part in _chunk_text(text):
                blocks.append({"object": "block", "type": "bulleted_list_item",
                               "bulleted_list_item": {"rich_text": _rich_text(part)}})
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_para()
            text = re.sub(r"^\d+\.\s+", "", stripped)
            for part in _chunk_text(text):
                blocks.append({"object": "block", "type": "numbered_list_item",
                               "numbered_list_item": {"rich_text": _rich_text(part)}})
            continue

        # 빈 줄 → 단락 종료
        if not stripped:
            flush_para()
            continue

        # 일반 문단 버퍼링
        para_buf.append(line)

    # 마무리
    if in_code:
        flush_code()
    flush_para()

    return blocks


# ============== Notion REST 호출 ==============
def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def _get_db_title_prop_name(db_id: str, token: str) -> str:
    if db_id in _DB_TITLE_PROP_CACHE:
        return _DB_TITLE_PROP_CACHE[db_id]
    resp = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=_headers(token), timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"DB 스키마 조회 실패({resp.status_code}): {resp.text}")
    data = resp.json()
    props = data.get("properties", {}) or {}
    for prop_name, schema in props.items():
        if schema.get("type") == "title":
            _DB_TITLE_PROP_CACHE[db_id] = prop_name
            return prop_name
    raise RuntimeError("해당 DB에 'title' 타입 속성이 없습니다.")

def _append_children(page_or_block_id: str, children: List[Dict[str, Any]], token: str) -> None:
    """children이 100개 제한을 넘으면 배치로 append."""
    for batch in _chunks(children, MAX_CHILDREN_PER_REQUEST):
        resp = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_or_block_id}/children",
            headers=_headers(token),
            json={"children": batch},
            timeout=60,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"children append 실패({resp.status_code}): {resp.text}")

def _create_page(parent_page_id: str, title: str, blocks: List[Dict[str, Any]], token: str) -> str:
    """일반 페이지 생성 + 모든 블록 삽입."""
    # 생성 시 첫 배치는 함께 보내고, 나머지는 append
    first = blocks[:MAX_CHILDREN_PER_REQUEST]
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_headers(token),
        json={
            "parent": {"page_id": parent_page_id},
            "properties": {"title": [{"type": "text", "text": {"content": title}}]},
            "children": first
        },
        timeout=60,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"페이지 생성 실패({resp.status_code}): {resp.text}")
    data = resp.json()
    page_id = data["id"]
    # 남은 블록 append
    rest = blocks[MAX_CHILDREN_PER_REQUEST:]
    if rest:
        _append_children(page_id, rest, token)
    return f"https://www.notion.so/{page_id.replace('-', '')}"

def _create_db_row(database_id: str, title_prop: str, title: str, blocks: List[Dict[str, Any]], token: str) -> str:
    """DB 행(페이지) 생성 + 모든 블록 삽입."""
    first = blocks[:MAX_CHILDREN_PER_REQUEST]
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=_headers(token),
        json={
            "parent": {"database_id": database_id},
            "properties": {title_prop: {"title": [{"type": "text", "text": {"content": title}}]}},
            "children": first
        },
        timeout=60,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"DB 행 생성 실패({resp.status_code}): {resp.text}")
    data = resp.json()
    page_id = data["id"]
    rest = blocks[MAX_CHILDREN_PER_REQUEST:]
    if rest:
        _append_children(page_id, rest, token)
    return f"https://www.notion.so/{page_id.replace('-', '')}"


# ============== 공개 API ==============
def save_answer_to_notion(
    title: str,
    markdown: str,
    meta: dict | None = None,   # 메타는 현재 미사용(필요 시 properties로 확장 가능)
    *,
    parent_url: str | None = None,
    db_url: str | None = None,
    save: bool | None = None,
) -> dict | None:
    """
    답변을 Notion에 "DB"와 "일반 페이지" 둘 다 저장.
    - parent_url이 있으면 일반 페이지 생성
    - db_url이 있으면 DB 행 생성
    - 둘 다 있으면 둘 다 생성
    - 반환: {"ok": True, "url": <우선 페이지 URL>, "url_page": ..., "url_db": ..., "created": [...], "debug": {...}}
    """
    dbg = _debug_snapshot()
    if save is False or dbg["save_flag"] is False:
        return {"ok": False, "reason": "save_flag_false", "debug": dbg}

    token = MCP_CFG.get("notion_api_token")
    if not token:
        return {"ok": False, "reason": "no_token", "error": "notion_api_token이 없습니다.", "debug": dbg}

    # 우선순위: 함수 인자 > 설정 파일
    parent_url = parent_url or MCP_CFG.get("parent_url")
    db_url = db_url or MCP_CFG.get("db_url")

    # Markdown → Blocks (절대 truncate 하지 않음)
    blocks = _markdown_to_blocks(markdown)

    created: List[str] = []
    url_page: Optional[str] = None
    url_db: Optional[str] = None

    # 1) 일반 페이지
    if parent_url:
        parent_id = _extract_page_id_from_url(parent_url)
        if not parent_id:
            return {"ok": False, "reason": "bad_parent_url", "error": f"parent_url ID 추출 실패: {parent_url}", "debug": dbg}
        try:
            url_page = _create_page(parent_id, title, blocks, token)
            created.append("page")
        except Exception as e:
            return {"ok": False, "reason": "page_create_failed", "error": str(e), "debug": dbg}

    # 2) DB 행
    if db_url:
        db_id = _extract_page_id_from_url(db_url)
        if not db_id:
            return {"ok": False, "reason": "bad_db_url", "error": f"db_url ID 추출 실패: {db_url}", "debug": dbg}
        try:
            title_prop = _get_db_title_prop_name(db_id, token)
            url_db = _create_db_row(db_id, title_prop, title, blocks, token)
            created.append("database")
        except Exception as e:
            return {"ok": False, "reason": "db_create_failed", "error": str(e), "debug": dbg}

    if not created:
        return {"ok": False, "reason": "no_target", "error": "parent_url과 db_url이 모두 비어 있습니다.", "debug": dbg}

    # 우선 반환 url은 '페이지'가 있으면 페이지, 없으면 DB
    return {
        "ok": True,
        "url": url_page or url_db,
        "url_page": url_page,
        "url_db": url_db,
        "created": created,
        "debug": dbg
    }
