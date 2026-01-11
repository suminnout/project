import json
import glob
import re
import os
import time
from sentence_transformers import SentenceTransformer
import weaviate
from weaviate.util import generate_uuid5
from weaviate.exceptions import UnexpectedStatusCodeException, ObjectAlreadyExistsException
import torch
from tqdm import tqdm  # ✅ 이걸로 수정반

# ✅ Weaviate 클라이언트 연결
client = weaviate.Client("http://localhost:8080")

# ✅ 임베딩 모델 (고정도 한국어)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
embed_model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS")
embed_model.to(device) 

#################################################################################################

def build_index():
    DATA_ROOT = "/home/tako/LIMJAEEUN/SW융합 해커톤/version1/data"

    # ===== 헬퍼: 청킹/표 평탄화 (기존 그대로) =====
    def chunk_text(text, max_chars=1200, overlap=200):
        if not text:
            return []
        sents = [s.strip() for s in re.split(r'(?<=[\.!?])\s+', text) if s.strip()]
        chunks, buf, cur = [], [], 0
        for s in sents:
            if cur + len(s) + 1 > max_chars and buf:
                whole = " ".join(buf)
                chunks.append(whole)
                tail = whole[-overlap:] if overlap > 0 else ""
                buf, cur = ([tail] if tail else []), len(tail)
            buf.append(s)
            cur += len(s) + 1
        if buf:
            chunks.append(" ".join(buf))
        return chunks or [text[:max_chars]]

    def flatten_table(table_rows):
        flat = []
        for row in table_rows or []:
            flat.append("; ".join([f"{k}:{v}" for k, v in row.items()]))
        return "\n".join(flat)

    def flatten_document(doc):
        title = doc.get("title", "")
        for chapter in doc.get("chapters", []):
            chapter_title = chapter.get("title", "")
            for section in chapter.get("sections", []):
                section_heading = section.get("heading", "")

                text_items = [item for item in section.get("contents", []) if isinstance(item, str)]
                aggregated_content = "\n".join(text_items).strip()

                table_items = [item["table"] for item in section.get("contents", [])
                               if isinstance(item, dict) and "table" in item]
                aggregated_table_json = json.dumps(table_items, ensure_ascii=False) if table_items else ""
                table_texts = [flatten_table(rows) for rows in table_items]

                embed_base = "\n".join([aggregated_content] + [t for t in table_texts if t]).strip()

                for pi, chunk in enumerate(chunk_text(embed_base, max_chars=1200, overlap=200), start=1):
                    yield {
                        "title": title,
                        "chapter_title": chapter_title,
                        "section_heading": section_heading,
                        "content": chunk,
                        "table_json": aggregated_table_json
                    }

    # ===== data 하위 폴더(=클래스) 반복 =====
    subdirs = [d for d in sorted(os.listdir(DATA_ROOT))
               if os.path.isdir(os.path.join(DATA_ROOT, d))]

    for folder in subdirs:
        class_name = folder  # 최소 변경: 폴더명 그대로 사용
        # 필요 시 1줄 정규화(주석 해제해서 사용): 클래스 규칙 위반 폴더명 대비
        # class_name = re.sub(r'[^0-9A-Za-z_]', '', class_name).strip() or "Class"
        # if not class_name[0].isalpha(): class_name = "C" + class_name

        print(f"\n📚 Building class '{class_name}' from folder '{folder}'")

        # 1) 기존 클래스 삭제 후 생성
        schema_now = client.schema.get()
        existing = [c["class"] for c in schema_now.get("classes", [])]
        if class_name in existing:
            try:
                client.schema.delete_class(class_name)
            except UnexpectedStatusCodeException as e:
                print(f"⚠️ delete failed for {class_name}: {e}", flush=True)
            else:
                # 삭제가 반영될 때까지 짧게 대기(최대 ~5초)
                for _ in range(20):
                    now = client.schema.get()
                    if class_name not in [c["class"] for c in now.get("classes", [])]:
                        break
                    time.sleep(0.25)

        schema = {
            "class": class_name,
            "vectorizer": "none",
            "moduleConfig": {},
            "properties": [
                {"name": "title", "dataType": ["text"]},
                {"name": "chapter_title", "dataType": ["text"]},
                {"name": "section_heading", "dataType": ["text"]},
                {"name": "content", "dataType": ["text"]},
                {"name": "table_json", "dataType": ["text"]},
            ],
            "vectorIndexConfig": {
                "distance": "cosine",
                "efConstruction": 200,
                "maxConnections": 64
            }
        }
        current = client.schema.get()
        current_classes = [c["class"] for c in current.get("classes", [])]

        if class_name in current_classes:
            # 여기로 오면 이미 클래스가 존재 -> 생성 스킵하고 바로 인서트로 진행
            print(f"ℹ️ class '{class_name}' already exists → skip create", flush=True)
        else:
            try:
                client.schema.create_class(schema)
            except UnexpectedStatusCodeException as e:
                # race로 인해 생성 순간에 이미 생겨버린 경우를 무시
                if "already exists" in str(e):
                    print(f"ℹ️ class '{class_name}' already exists (race) → continue", flush=True)
                else:
                    raise

        # 2) 폴더 내 모든 JSON 재귀 수집
        json_files = glob.glob(os.path.join(DATA_ROOT, folder, "**", "*.json"), recursive=True)
        if not json_files:
            print("  ⚠️ no json files, skip")
            continue

        # 3) 파일별 로드 → 플랫 → 인서트
        inserted = 0
        for path in tqdm(json_files, desc=f"[{class_name}] files", unit="file"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"  ⚠️ load fail: {path} ({e})")
                continue

            if isinstance(data, dict):
                entries = list(flatten_document(data))
            elif isinstance(data, list):
                entries = []
                for d in data:
                    if isinstance(d, dict):
                        entries.extend(list(flatten_document(d)))
            else:
                continue

            for doc_obj in tqdm(entries, desc=f"[{class_name}] insert", leave=False):
                text_to_embed = (doc_obj.get("content") or "").strip()
                if not text_to_embed:
                    continue
                try:
                    vec = embed_model.encode(text_to_embed, convert_to_numpy=True)
                except Exception as e:
                    print(f"  ⚠️ embed fail: {e}")
                    continue

                # 🔸 최소 변경 1줄: 클래스명을 basis에 포함해 클래스 간 UUID 충돌 방지
                basis = f"{class_name}|{doc_obj.get('title','')}|{doc_obj.get('chapter_title','')}|{doc_obj.get('section_heading','')}|{text_to_embed}"
                uuid = generate_uuid5(basis)

                try:
                    client.data_object.create(
                        data_object=doc_obj,
                        class_name=class_name,
                        uuid=uuid,
                        vector=vec
                    )
                    inserted += 1
                except ObjectAlreadyExistsException:
                    # 이미 있으면 교체(업데이트)
                    client.data_object.replace(
                        data_object=doc_obj,
                        class_name=class_name,
                        uuid=uuid,
                        vector=vec
                    )
                except Exception as e:
                    print(f"  ⚠️ insert fail: {e}")

        print(f"✅ {class_name}: inserted {inserted} objects")

    print("\n🎉 모든 폴더 인덱싱 완료")

if __name__ == "__main__":
    build_index()