# -*- coding: utf-8 -*-
"""
Fault 向量：OpenAI 兼容 /v1/embeddings + Qdrant collection `fault_vectors`。
供 main.py 的 /admin/fault-vectors/sync 与 /graph/recommend 使用。
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6334").rstrip("/")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "fault_vectors")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "").rstrip("/")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
# 与所用模型一致；OpenAI text-embedding-3-small 默认 1536
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
REQUEST_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "60"))

GremlinFn = Callable[[str, Optional[Dict[str, Any]]], Dict[str, Any]]
ExtractFn = Callable[[Dict[str, Any]], List[Any]]


def _openai_api_origin(url: str) -> str:
    """
    从「根地址 / …/v1 / …/chat/completions」等推到用于拼 `/v1/embeddings` 的 origin（末尾不含 /v1）。
    例：https://api.openai.com/v1/chat/completions -> https://api.openai.com
    """
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    low = u.lower()
    for suf in ("/v1/chat/completions", "/chat/completions"):
        if low.endswith(suf):
            u = u[: -len(suf)].rstrip("/")
            low = u.lower()
            break
    if low.endswith("/v1/embeddings"):
        u = u[: -len("/v1/embeddings")].rstrip("/")
        low = u.lower()
    if low.endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u


def _embedding_base_url() -> str:
    """用于拼 {origin}/v1/embeddings；优先 EMBEDDING_API_URL，否则从 LLM_API_URL 推导。"""
    raw = (EMBEDDING_API_URL or os.getenv("LLM_API_URL", "")).strip()
    return _openai_api_origin(raw)


def _embedding_auth_header() -> str:
    key = EMBEDDING_API_KEY or os.getenv("LLM_API_KEY", "")
    return key


def embedding_configured() -> bool:
    return bool(_embedding_base_url() and _embedding_auth_header())


def fault_embedding_text(name: str, description: str, domain: str = "") -> str:
    parts = [name.strip()]
    if domain.strip():
        parts.append(f"领域: {domain.strip()}")
    d = (description or "").strip()
    if d:
        parts.append(d[:2000])
    return "\n".join(parts)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """OpenAI 兼容 POST {base}/v1/embeddings，返回与输入顺序一致的向量列表。"""
    if not texts:
        return []
    base = _embedding_base_url()
    key = _embedding_auth_header()
    if not base or not key:
        raise RuntimeError("Embedding API URL 或 API Key 未配置（EMBEDDING_* 或 LLM_*）")

    url = f"{base.rstrip('/')}/v1/embeddings"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        raise RuntimeError(f"Embeddings HTTP {resp.status_code}: {resp.text[:500]}")

    data = resp.json().get("data") or []
    # 按 index 排序
    indexed = sorted(data, key=lambda x: int(x.get("index", 0)))
    vectors: List[List[float]] = []
    for item in indexed:
        vec = item.get("embedding")
        if not isinstance(vec, list):
            raise RuntimeError("Invalid embeddings response: missing embedding[]")
        vectors.append([float(x) for x in vec])
    if len(vectors) != len(texts):
        raise RuntimeError(f"Embeddings count mismatch: got {len(vectors)}, want {len(texts)}")
    return vectors


def _qdrant_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=QDRANT_URL, timeout=30)


def _collection_vector_dim(client: object, name: str) -> Optional[int]:
    try:
        info = client.get_collection(name)
        vec = info.config.params.vectors
        if hasattr(vec, "size"):
            return int(vec.size)
        if isinstance(vec, dict) and vec:
            first = next(iter(vec.values()))
            if hasattr(first, "size"):
                return int(first.size)
    except Exception:
        return None
    return None


def ensure_fault_collection(vector_dim: int) -> None:
    from qdrant_client.http import models as qm

    client = _qdrant_client()
    names = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION in names:
        existing = _collection_vector_dim(client, QDRANT_COLLECTION)
        if existing is not None and existing != int(vector_dim):
            client.delete_collection(QDRANT_COLLECTION)
            names.discard(QDRANT_COLLECTION)
    names = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION not in names:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qm.VectorParams(size=vector_dim, distance=qm.Distance.COSINE),
        )


def qdrant_collection_point_count() -> int:
    try:
        client = _qdrant_client()
        names = [c.name for c in client.get_collections().collections]
        if QDRANT_COLLECTION not in names:
            return 0
        info = client.get_collection(QDRANT_COLLECTION)
        return int(getattr(info, "points_count", 0) or 0)
    except Exception:
        return 0


def search_similar_faults(
    query_text: str,
    top_k: int,
) -> List[Tuple[str, float]]:
    """
    向量检索，返回 [(fault_name, score), ...]，score 为 Qdrant cosine 分数（越大越相似）。
    """
    if not embedding_configured():
        return []
    vecs = embed_texts([query_text])
    if not vecs:
        return []
    qv = vecs[0]

    client = _qdrant_client()
    names = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in names:
        return []

    try:
        hits = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=qv,
            limit=top_k,
            with_payload=True,
        )
    except Exception:
        return []

    out: List[Tuple[str, float]] = []
    for h in hits:
        fn = (h.payload or {}).get("fault_name")
        if isinstance(fn, str) and fn.strip():
            out.append((fn.strip(), float(h.score)))
    return out


def sync_fault_vectors_from_graph(
    execute_gremlin: GremlinFn,
    extract_data: ExtractFn,
    full_reset: bool = False,
) -> Dict[str, Any]:
    """
    从 HugeGraph 读取 Fault（name + description + domain），写入 Qdrant。
    full_reset=True 时先删 collection 再全量重建（去除已删除故障的脏点）。
    """
    if not embedding_configured():
        raise RuntimeError("未配置 Embedding API：请设置 EMBEDDING_API_URL+EMBEDDING_API_KEY，或 LLM_API_URL+LLM_API_KEY")

    script = """
g.V().hasLabel('Fault').project('name','description','domain').
  by(values('name')).
  by(coalesce(values('description'), constant(''))).
  by(coalesce(values('domain'), constant('')))
"""
    rows = extract_data(execute_gremlin(script))
    faults: List[Dict[str, str]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        faults.append({
            "name":        name,
            "description": str(row.get("description") or ""),
            "domain":      str(row.get("domain") or ""),
        })

    if not faults:
        return {
            "status":     "ok",
            "message":    "图中无 Fault，未写入 Qdrant",
            "upserted":   0,
            "collection": QDRANT_COLLECTION,
        }

    texts = [fault_embedding_text(f["name"], f["description"], f["domain"]) for f in faults]
    # 探测维度
    probe = embed_texts([texts[0]])
    dim = len(probe[0])

    client = _qdrant_client()
    if full_reset:
        try:
            client.delete_collection(QDRANT_COLLECTION)
        except Exception:
            pass

    ensure_fault_collection(dim)

    from qdrant_client.models import PointStruct

    batch_size = 32
    upserted = 0
    for i in range(0, len(texts), batch_size):
        chunk_texts = texts[i : i + batch_size]
        chunk_faults = faults[i : i + batch_size]
        vectors = embed_texts(chunk_texts)
        points: List[PointStruct] = []
        for f, text, vec in zip(chunk_faults, chunk_texts, vectors):
            pid = str(uuid.uuid5(uuid.NAMESPACE_URL, "wisops:fault:" + f["name"]))
            points.append(
                PointStruct(
                    id=pid,
                    vector=vec,
                    payload={
                        "fault_name": f["name"],
                        "domain":     f["domain"],
                        "embed_text": text[:500],
                    },
                )
            )
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        upserted += len(points)

    return {
        "status":       "ok",
        "collection":   QDRANT_COLLECTION,
        "vector_dim":   dim,
        "model":        EMBEDDING_MODEL,
        "faults_in_graph": len(faults),
        "upserted":     upserted,
        "qdrant_url":   QDRANT_URL,
    }


def upsert_fault_vector_for_name(
    execute_gremlin: GremlinFn,
    extract_data: ExtractFn,
    fault_name: str,
) -> bool:
    """
    将单个 Fault 写入/更新到 Qdrant（与全量 sync 同一套 point id 与 payload）。
    未配置 embedding、图中无该 Fault、或已有 collection 的向量维度与当前模型不一致时返回 False（不删库）。
    """
    if not embedding_configured():
        return False
    fn = (fault_name or "").strip()
    if not fn:
        return False
    script = """
g.V().hasLabel('Fault').has('name', fault_name).limit(1).
  project('name','description','domain').
  by(values('name')).
  by(coalesce(values('description'), constant(''))).
  by(coalesce(values('domain'), constant('')))
"""
    rows = extract_data(execute_gremlin(script, {"fault_name": fn}))
    if not rows or not isinstance(rows[0], dict):
        return False
    row = rows[0]
    name = str(row.get("name") or "").strip()
    if not name:
        return False
    f = {
        "name":          name,
        "description":   str(row.get("description") or ""),
        "domain":        str(row.get("domain") or ""),
    }
    text = fault_embedding_text(f["name"], f["description"], f["domain"])
    vec = embed_texts([text])[0]
    dim = len(vec)

    client = _qdrant_client()
    names = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION not in names:
        ensure_fault_collection(dim)
    else:
        existing = _collection_vector_dim(client, QDRANT_COLLECTION)
        if existing is None or int(existing) != int(dim):
            return False

    from qdrant_client.models import PointStruct

    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, "wisops:fault:" + f["name"]))
    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=pid,
                vector=vec,
                payload={
                    "fault_name": f["name"],
                    "domain":     f["domain"],
                    "embed_text": text[:500],
                },
            )
        ],
    )
    return True
