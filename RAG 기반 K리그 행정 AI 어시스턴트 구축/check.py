import weaviate

client = weaviate.Client("http://localhost:8080")

# 전체 스키마 출력
schema = client.schema.get()
print("Full schema:", schema)

# 특정 클래스 정보만
cls = client.schema.get("Soccer")
print("Soccer class schema:", cls)

query = """
{
  Aggregate {
    Soccer {
      meta {
        count
      }
    }
  }
}
"""
result = client.query.raw(query)
print("Object count:", result)

from sentence_transformers import SentenceTransformer
import torch
import weaviate
import pprint

# Weaviate client
client = weaviate.Client(url="http://localhost:8080", startup_period=30)

# SBERT 모델
device      = torch.device("cuda" if torch.cuda.is_available() else "cpu")
embed_model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS").to(device)

# 질의
query = "선수 최저 연봉에 대해 알려줘"

# 1) 제목 임베딩 생성
title_vec = embed_model.encode(query, convert_to_numpy=True)
# 1차: 제목 벡터로 ANN 탐색 (K1=20)
stage1 = client.query.get(
    "Soccer", 
    ["_additional { id }"]
).with_near_vector({
    "vector": title_vec,
    "certainty": 0.7
}).with_limit(20).do()

ids = [item["_additional"]["id"] for item in stage1["data"]["Get"]["Soccer"]]

# 2) 본문 임베딩 생성
content_vec = embed_model.encode(query, convert_to_numpy=True)
# 2차: ID 필터 + 본문 벡터로 ANN 탐색 (K2=5)
where_filter = {
    "path":             ["id"],
    "operator":         "ContainsAny",
    "valueStringArray": ids
}

final = client.query.get(
    "Soccer",
    ["title", "chapter_title", "section_heading", "content", "table_json"]
).with_where(where_filter) \
 .with_near_vector({
     "vector": content_vec,
     "certainty": 0.7
 }).with_limit(5).do()

pprint.pprint(final)
