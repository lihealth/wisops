"""WisOps Graph API — V2.0"""
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
import vector_search as _vec
from fastapi import Body, FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

app = FastAPI(
    title="WisOps Graph API",
    version="2.0.0",
    root_path="/graph-api",
    root_path_in_servers=False,
)

HUGEGRAPH_URL   = os.getenv("HUGEGRAPH_URL",   "http://localhost:8081").rstrip("/")
HUGEGRAPH_GRAPH = os.getenv("HUGEGRAPH_GRAPH", "hugegraph")
LLM_API_URL     = os.getenv("LLM_API_URL",     "")          # 可选外部 LLM（兼容 OpenAI Chat API）
LLM_API_KEY     = os.getenv("LLM_API_KEY",     "")
# 聊天/抽取所用模型名（DeepSeek 填如 deepseek-chat；OpenAI 填 gpt-4o-mini 等）
LLM_CHAT_MODEL  = os.getenv("LLM_CHAT_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = 10

_ACTIVE_GREMLIN_ENDPOINT: Optional[str] = None

# 内存审核队列（生产可替换为 Redis/DB）
_extract_queue: Dict[str, Dict[str, Any]] = {}
# 抽取任务状态
_extract_jobs: Dict[str, Dict[str, Any]] = {}


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────────────────────────────────────

class AddRelationRequest(BaseModel):
    fault_name:           str   = Field(..., min_length=1, max_length=200)
    solution_name:        str   = Field(..., min_length=1, max_length=200)
    solution_description: str   = Field(default="", max_length=2000)
    steps:                str   = Field(default="")
    domain:               str   = Field(default="")
    data_source:          str   = Field(default="manual")
    confidence:           float = Field(default=1.0, ge=0.0, le=1.0)
    import_batch_id:      str   = Field(default="")

class SOPRequest(BaseModel):
    title:        str        = Field(..., min_length=1, max_length=300)
    fault_name:   str        = Field(..., min_length=1, max_length=200)
    steps:        List[str]  = Field(..., min_items=1)
    version:      str        = Field(default="1.0")
    author:       str        = Field(default="")
    data_source:  str        = Field(default="manual")

class AssetRequest(BaseModel):
    asset_id:   str = Field(..., min_length=1, max_length=200)
    name:       str = Field(default="")
    asset_type: str = Field(default="server")
    ip:         str = Field(default="")
    env:        str = Field(default="prod")
    data_source: str = Field(default="manual")

class AlertIngestRequest(BaseModel):
    alert_id:    str = Field(..., min_length=1, max_length=200)
    asset_id:    str = Field(default="")
    content:     str = Field(..., min_length=1, max_length=2000)
    level:       str = Field(default="P2")
    source:      str = Field(default="manual")
    occurred_at: Optional[int] = None   # Unix timestamp ms
    data_source: str = Field(default="manual")

class IncidentRequest(BaseModel):
    incident_id:  str = Field(..., min_length=1, max_length=200)
    title:        str = Field(..., min_length=1, max_length=500)
    fault_name:   Optional[str] = None
    solution_name: Optional[str] = None
    asset_id:     Optional[str] = None
    mttr_minutes: int = Field(default=0, ge=0)
    data_source:  str = Field(default="manual")

class ExtractSubmitRequest(BaseModel):
    text:        str = Field(..., min_length=10, max_length=50000)
    source_hint: str = Field(default="manual")  # 来源说明（文件名/工单 ID 等）

class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class CategorySeed(BaseModel):
    code:   str = Field(..., min_length=1, max_length=64)
    name:   str = Field(..., min_length=1, max_length=200)
    domain: str = Field(default="", max_length=200)


class CategoriesBootstrapRequest(BaseModel):
    """留空 categories 时使用内置 ITIL 风格分类"""
    categories: Optional[List[CategorySeed]] = None


# 内置分类（与 Fault.domain 常见取值对齐，code 主键）
DEFAULT_ITIL_CATEGORIES: List[Dict[str, str]] = [
    {"code": "CAT-APP",  "name": "应用",     "domain": "Application"},
    {"code": "CAT-DB",   "name": "数据库",   "domain": "Database"},
    {"code": "CAT-STOR", "name": "存储",     "domain": "Storage"},
    {"code": "CAT-SEC",  "name": "安全",     "domain": "Security"},
    {"code": "CAT-NET",  "name": "网络",     "domain": "Network"},
    {"code": "CAT-MW",   "name": "中间件",   "domain": "Middleware"},
    {"code": "CAT-K8S",  "name": "Kubernetes", "domain": "Kubernetes"},
    {"code": "CAT-GEN",  "name": "通用",     "domain": ""},
]

# Fault 顶点 domain 属性 → Category.code
DOMAIN_TO_CATEGORY_CODE: Dict[str, str] = {
    "Application": "CAT-APP",
    "Database":    "CAT-DB",
    "Storage":     "CAT-STOR",
    "Security":    "CAT-SEC",
    "Network":     "CAT-NET",
    "Middleware":  "CAT-MW",
    "Kubernetes":  "CAT-K8S",
}


# ──────────────────────────────────────────────────────────────────────────────
# Gremlin 执行层
# ──────────────────────────────────────────────────────────────────────────────

def _candidate_gremlin_endpoints() -> List[str]:
    return [
        f"{HUGEGRAPH_URL}/graphs/{HUGEGRAPH_GRAPH}/gremlin",
        f"{HUGEGRAPH_URL}/gremlin",
        f"{HUGEGRAPH_URL}/graphs/hugegraph/gremlin",
    ]


def execute_gremlin(gremlin: str, bindings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    global _ACTIVE_GREMLIN_ENDPOINT
    gremlin = re.sub(r"\bgraph\.traversal\(\)", f"{HUGEGRAPH_GRAPH}.traversal()", gremlin)
    gremlin = re.sub(r"\bgraph\.schema\(\)",    f"{HUGEGRAPH_GRAPH}.schema()",    gremlin)
    if "traversal()" not in gremlin and "schema()" not in gremlin:
        gremlin = f"def g = {HUGEGRAPH_GRAPH}.traversal();\n" + gremlin

    endpoints = [_ACTIVE_GREMLIN_ENDPOINT] if _ACTIVE_GREMLIN_ENDPOINT else []
    endpoints.extend([ep for ep in _candidate_gremlin_endpoints() if ep != _ACTIVE_GREMLIN_ENDPOINT])

    last_error: Optional[str] = None
    for endpoint in endpoints:
        try:
            resp = requests.post(
                endpoint,
                json={"gremlin": gremlin, "bindings": bindings or {}},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = f"{endpoint} -> {exc}"
            continue
        if resp.status_code == 404:
            last_error = f"{endpoint} -> HTTP 404"
            continue
        if not resp.ok:
            raise HTTPException(status_code=502, detail=f"HugeGraph error {resp.status_code}: {resp.text}")
        _ACTIVE_GREMLIN_ENDPOINT = endpoint
        return resp.json()

    raise HTTPException(status_code=503, detail=f"HugeGraph unavailable: {last_error}")


def _extract_data(payload: Dict[str, Any]) -> List[Any]:
    result = payload.get("result", {})
    data = result.get("data", [])
    return data if isinstance(data, list) else []


def ensure_schema_v2() -> None:
    """幂等执行 V2.0 Schema 初始化（兼容已存在的 V1.x 顶点标签）"""
    script = """
schema = hugegraph.schema()
// 属性键（全部幂等）
schema.propertyKey('name').asText().ifNotExist().create()
schema.propertyKey('description').asText().ifNotExist().create()
schema.propertyKey('title').asText().ifNotExist().create()
schema.propertyKey('steps').asText().ifNotExist().create()
schema.propertyKey('version').asText().ifNotExist().create()
schema.propertyKey('author').asText().ifNotExist().create()
schema.propertyKey('domain').asText().ifNotExist().create()
schema.propertyKey('category').asText().ifNotExist().create()
schema.propertyKey('severity').asText().ifNotExist().create()
schema.propertyKey('data_source').asText().ifNotExist().create()
schema.propertyKey('confidence').asDouble().ifNotExist().create()
schema.propertyKey('import_batch_id').asText().ifNotExist().create()
schema.propertyKey('created_at').asLong().ifNotExist().create()
schema.propertyKey('score').asDouble().ifNotExist().create()
schema.propertyKey('chunk_ref').asText().ifNotExist().create()
schema.propertyKey('asset_id').asText().ifNotExist().create()
schema.propertyKey('asset_type').asText().ifNotExist().create()
schema.propertyKey('ip').asText().ifNotExist().create()
schema.propertyKey('env').asText().ifNotExist().create()
schema.propertyKey('alert_id').asText().ifNotExist().create()
schema.propertyKey('content').asText().ifNotExist().create()
schema.propertyKey('level').asText().ifNotExist().create()
schema.propertyKey('source').asText().ifNotExist().create()
schema.propertyKey('occurred_at').asLong().ifNotExist().create()
schema.propertyKey('incident_id').asText().ifNotExist().create()
schema.propertyKey('status').asText().ifNotExist().create()
schema.propertyKey('closed_at').asLong().ifNotExist().create()
schema.propertyKey('mttr_minutes').asInt().ifNotExist().create()
schema.propertyKey('username').asText().ifNotExist().create()
schema.propertyKey('team').asText().ifNotExist().create()
schema.propertyKey('expertise').asText().ifNotExist().create()
schema.propertyKey('code').asText().ifNotExist().create()
schema.propertyKey('method').asText().ifNotExist().create()
schema.propertyKey('role').asText().ifNotExist().create()
schema.propertyKey('adopted_at').asLong().ifNotExist().create()

// Fault / Solution：仅在不存在时创建（已存在的之前已手动修复）
def existingV1Labels = schema.getVertexLabels().collect { it.name() } as Set
if (!existingV1Labels.contains('Fault')) {
  schema.vertexLabel('Fault').properties('name','description','category','severity','domain','data_source','confidence','import_batch_id','created_at').primaryKeys('name').nullableKeys('description','category','severity','domain','data_source','confidence','import_batch_id','created_at').create()
}
if (!existingV1Labels.contains('Solution')) {
  schema.vertexLabel('Solution').properties('name','description','steps','data_source','confidence','import_batch_id','created_at').primaryKeys('name').nullableKeys('description','steps','data_source','confidence','import_batch_id','created_at').create()
}

// SOP / Asset / Alert / Incident / Person / Category
def existingVertexLabels = schema.getVertexLabels().collect { it.name() } as Set
if (!existingVertexLabels.contains('SOP')) {
  schema.vertexLabel('SOP').properties('name','title','steps','version','author','data_source','confidence','created_at').primaryKeys('name').nullableKeys('title','steps','version','author','data_source','confidence','created_at').create()
}
if (!existingVertexLabels.contains('Asset')) {
  schema.vertexLabel('Asset').properties('asset_id','asset_type','name','ip','env','data_source','created_at').primaryKeys('asset_id').nullableKeys('asset_type','name','ip','env','data_source','created_at').create()
}
if (!existingVertexLabels.contains('Alert')) {
  schema.vertexLabel('Alert').properties('alert_id','content','level','source','occurred_at','status','data_source','created_at').primaryKeys('alert_id').nullableKeys('content','level','source','occurred_at','status','data_source','created_at').create()
} else {
  schema.vertexLabel('Alert').properties('data_source').nullableKeys('data_source').append()
}
if (!existingVertexLabels.contains('Incident')) {
  schema.vertexLabel('Incident').properties('incident_id','title','status','created_at','closed_at','mttr_minutes').primaryKeys('incident_id').nullableKeys('title','status','created_at','closed_at','mttr_minutes').create()
}
if (!existingVertexLabels.contains('Person')) {
  schema.vertexLabel('Person').properties('username','team','expertise').primaryKeys('username').nullableKeys('team','expertise').create()
}
if (!existingVertexLabels.contains('Category')) {
  schema.vertexLabel('Category').properties('code','name','domain').primaryKeys('code').nullableKeys('name','domain').create()
}

// 边标签：列表内已存在的跳过；不存在的创建
def existingEdgeLabels = schema.getEdgeLabels().collect { it.name() } as Set
if (!existingEdgeLabels.contains('HAS_SOLUTION')) {
  schema.edgeLabel('HAS_SOLUTION').sourceLabel('Fault').targetLabel('Solution').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('HAS_SOP')) {
  schema.edgeLabel('HAS_SOP').sourceLabel('Fault').targetLabel('SOP').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('SIMILAR_TO')) {
  schema.edgeLabel('SIMILAR_TO').sourceLabel('Fault').targetLabel('Fault').properties('score','method').nullableKeys('score','method').create()
}
if (!existingEdgeLabels.contains('HAS_ALERT')) {
  schema.edgeLabel('HAS_ALERT').sourceLabel('Asset').targetLabel('Alert').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('TRIGGERS')) {
  schema.edgeLabel('TRIGGERS').sourceLabel('Alert').targetLabel('Fault').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('INVOLVES')) {
  schema.edgeLabel('INVOLVES').sourceLabel('Incident').targetLabel('Asset').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('CAUSED_BY')) {
  schema.edgeLabel('CAUSED_BY').sourceLabel('Incident').targetLabel('Fault').properties('confidence').nullableKeys('confidence').create()
}
if (!existingEdgeLabels.contains('RESOLVED_BY')) {
  schema.edgeLabel('RESOLVED_BY').sourceLabel('Incident').targetLabel('Solution').properties('adopted_at').nullableKeys('adopted_at').create()
}
if (!existingEdgeLabels.contains('CLASSIFIED_AS')) {
  schema.edgeLabel('CLASSIFIED_AS').sourceLabel('Fault').targetLabel('Category').properties('created_at').nullableKeys('created_at').create()
}
if (!existingEdgeLabels.contains('DOCUMENTED_IN')) {
  schema.edgeLabel('DOCUMENTED_IN').sourceLabel('Solution').targetLabel('SOP').properties('chunk_ref').nullableKeys('chunk_ref').create()
}
if (!existingEdgeLabels.contains('CONTRIBUTED')) {
  schema.edgeLabel('CONTRIBUTED').sourceLabel('Person').targetLabel('Solution').properties('role','adopted_at').nullableKeys('role','adopted_at').create()
}
if (!existingEdgeLabels.contains('HANDLED_BY')) {
  schema.edgeLabel('HANDLED_BY').sourceLabel('Incident').targetLabel('Person').properties('role').nullableKeys('role').create()
}
"schema_v2_ok"
"""
    execute_gremlin(script)


def _ensure_schema_v1() -> None:
    """Fallback：仅初始化 V1.x 核心 Schema"""
    script = """
schema = graph.schema()
schema.propertyKey('name').asText().ifNotExist().create()
schema.propertyKey('description').asText().ifNotExist().create()
schema.propertyKey('data_source').asText().ifNotExist().create()
schema.propertyKey('confidence').asDouble().ifNotExist().create()
schema.propertyKey('import_batch_id').asText().ifNotExist().create()
schema.propertyKey('created_at').asLong().ifNotExist().create()
schema.vertexLabel('Fault').properties('name','description','data_source','confidence','import_batch_id','created_at').primaryKeys('name').ifNotExist().create()
schema.vertexLabel('Solution').properties('name','description','data_source','confidence','import_batch_id','created_at').primaryKeys('name').ifNotExist().create()
schema.edgeLabel('HAS_SOLUTION').sourceLabel('Fault').targetLabel('Solution').ifNotExist().create()
"""
    execute_gremlin(script)


@app.on_event("startup")
def startup() -> None:
    try:
        ensure_schema_v2()
    except HTTPException:
        pass


@app.post("/admin/schema/init")
def admin_schema_init() -> Dict[str, Any]:
    """手动触发 V2 Schema 初始化（暴露详细错误）"""
    ensure_schema_v2()
    return {"status": "ok"}


def _upsert_category(code: str, name: str, domain: str) -> str:
    find = execute_gremlin(
        "g.V().hasLabel('Category').has('code', ccode).id()",
        {"ccode": code},
    )
    ids = _extract_data(find)
    if ids:
        return str(ids[0])
    result = execute_gremlin(
        "g.addV('Category').property('code', ccode).property('name', cname).property('domain', cdom).id()",
        {"ccode": code, "cname": name, "cdom": domain},
    )
    ids = _extract_data(result)
    return str(ids[0]) if ids else ""


def _link_classified_as(fault_vid: str, category_vid: str, ts: int) -> bool:
    chk = execute_gremlin(
        "g.V(fvid).outE('CLASSIFIED_AS').where(__.inV().hasId(cid)).count()",
        {"fvid": fault_vid, "cid": category_vid},
    )
    if (_extract_data(chk) or [0])[0] > 0:
        return False
    execute_gremlin(
        "def fv = g.V(fvid).next(); def cv = g.V(cid).next(); "
        "g.addE('CLASSIFIED_AS').from(fv).to(cv).property('created_at', ts).iterate()",
        {"fvid": fault_vid, "cid": category_vid, "ts": ts},
    )
    return True


@app.post("/admin/categories/init")
def admin_categories_init(
    payload: Optional[CategoriesBootstrapRequest] = Body(default=None),
) -> Dict[str, Any]:
    """
    幂等：写入 Category 顶点，并按 Fault.domain 补 CLASSIFIED_AS 边。
    Body 可选：{"categories":[{"code":"...","name":"...","domain":"..."}]}
    """
    ensure_schema_v2()
    now = int(time.time() * 1000)
    if payload and payload.categories:
        seeds = payload.categories
    else:
        seeds = [CategorySeed(**c) for c in DEFAULT_ITIL_CATEGORIES]

    cat_ids: Dict[str, str] = {}
    for s in seeds:
        cid = _upsert_category(s.code, s.name, s.domain)
        if cid:
            cat_ids[s.code] = cid

    linked = 0
    fault_rows = _extract_data(
        execute_gremlin(
            "g.V().hasLabel('Fault').project('vid','dom').by(id()).by(coalesce(values('domain'), constant('')))"
        )
    )
    for row in fault_rows or []:
        if not isinstance(row, dict):
            continue
        fvid = str(row.get("vid", ""))
        dom  = (row.get("dom") or "").strip()
        code = DOMAIN_TO_CATEGORY_CODE.get(dom, "CAT-GEN")
        cid  = cat_ids.get(code) or cat_ids.get("CAT-GEN")
        if fvid and cid and _link_classified_as(fvid, cid, now):
            linked += 1

    return {
        "status":           "ok",
        "categories_upserted": len(seeds),
        "classified_as_created": linked,
    }


def _score_alert_fault_match(content: str, fault_name: str) -> float:
    if not content or not fault_name:
        return 0.0
    c = content.lower()
    base = re.sub(r"[（(][^)）]*[)）]", "", fault_name).strip().lower()
    if base and len(base) >= 3 and base in c:
        return 1.0
    if fault_name.lower() in c:
        return 0.95
    for w in re.findall(r"[a-z]{3,}", fault_name.lower()):
        if len(w) >= 4 and w in c:
            return 0.85
    zh = re.sub(r"[^\u4e00-\u9fff]+", "", fault_name)
    if len(zh) >= 4:
        for i in range(0, len(zh) - 3):
            if zh[i : i + 4] in content:
                return 0.75
    return 0.0


@app.post("/admin/triggers/sync")
def admin_triggers_sync(top_k_per_alert: int = 2) -> Dict[str, Any]:
    """
    按告警文本与故障名模糊匹配，批量补 TRIGGERS 边（幂等，已存在则跳过）。
    top_k_per_alert：每条告警最多关联几条故障（query，默认 2，最大 5）。
    """
    ensure_schema_v2()
    now = int(time.time() * 1000)
    top_k = max(1, min(int(top_k_per_alert), 5))

    faults_raw = _extract_data(
        execute_gremlin(
            "g.V().hasLabel('Fault').project('vid','name').by(id()).by(values('name'))"
        )
    )
    faults: List[Dict[str, str]] = []
    for row in faults_raw or []:
        if isinstance(row, dict) and row.get("vid") and row.get("name"):
            faults.append({"vid": str(row["vid"]), "name": str(row["name"])})

    alerts_raw = _extract_data(
        execute_gremlin(
            "g.V().hasLabel('Alert').project('vid','c').by(id()).by(coalesce(values('content'), constant('')))"
        )
    )
    alerts: List[Dict[str, str]] = []
    for row in alerts_raw or []:
        if isinstance(row, dict) and row.get("vid"):
            alerts.append({"vid": str(row["vid"]), "c": str(row.get("c") or "")})

    created = 0
    skipped = 0
    for al in alerts:
        content = al["c"]
        scored: List[tuple] = []
        for f in faults:
            sc = _score_alert_fault_match(content, f["name"])
            if sc >= 0.72:
                scored.append((sc, f["vid"]))
        scored.sort(key=lambda x: -x[0])
        for _, fvid in scored[:top_k]:
            chk = execute_gremlin(
                "g.V(aid).outE('TRIGGERS').where(__.inV().hasId(fid)).count()",
                {"aid": al["vid"], "fid": fvid},
            )
            if (_extract_data(chk) or [0])[0] > 0:
                skipped += 1
                continue
            try:
                execute_gremlin(
                    "def av = g.V(aid).next(); def fv = g.V(fid).next(); "
                    "g.addE('TRIGGERS').from(av).to(fv).property('created_at', ts).iterate()",
                    {"aid": al["vid"], "fid": fvid, "ts": now},
                )
                created += 1
            except HTTPException:
                pass

    return {
        "status":         "ok",
        "alerts_scanned": len(alerts),
        "faults_indexed": len(faults),
        "triggers_created": created,
        "triggers_skip_exists": skipped,
    }


@app.post("/admin/fault-vectors/sync")
def admin_fault_vectors_sync(full_reset: bool = False) -> Dict[str, Any]:
    """
    将 HugeGraph 中 Fault（name + description + domain）向量化并 upsert 到 Qdrant collection（默认 fault_vectors）。
    需配置 EMBEDDING_API_URL + EMBEDDING_API_KEY，或复用 LLM_API_URL + LLM_API_KEY（OpenAI 兼容 /v1/embeddings）。
    full_reset=true 时先删除 collection 再重建，用于换 embedding 模型或清理脏点。
    """
    ensure_schema_v2()
    try:
        return _vec.sync_fault_vectors_from_graph(execute_gremlin, _extract_data, full_reset=full_reset)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"fault-vectors sync failed: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# V1.x 接口（保留，兼容）
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, str]:
    try:
        execute_gremlin("g.V().limit(1)")
        return {"status": "ok", "hugegraph": "connected", "api_version": "2.0"}
    except HTTPException:
        return {"status": "degraded", "hugegraph": "disconnected", "api_version": "2.0"}


def _upsert_vertex(label: str, name: str, extra_props: Dict[str, Any]) -> str:
    """查找或创建顶点，返回顶点 ID（字符串）"""
    find = execute_gremlin(
        "g.V().hasLabel(lbl).has('name', vname).id()",
        {"lbl": label, "vname": name},
    )
    ids = _extract_data(find)
    if ids:
        return str(ids[0])

    # 构造 property 链
    now = int(time.time() * 1000)
    props = {"vname": name, "ts": now}
    prop_chain = ".property('name', vname).property('created_at', ts)"
    for k, v in extra_props.items():
        props[k] = v
        prop_chain += f".property('{k}', {k})"

    script = f"g.addV(lbl){prop_chain}.id()"
    props["lbl"] = label
    result = execute_gremlin(script, props)
    ids = _extract_data(result)
    return str(ids[0]) if ids else ""


@app.post("/graph/add")
def add_relation(payload: AddRelationRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    # 1. 确保 Fault 顶点存在
    fid = _upsert_vertex("Fault", payload.fault_name, {
        "data_source": payload.data_source,
        "confidence":  payload.confidence,
        "domain":      payload.domain,
    })
    if not fid:
        raise HTTPException(status_code=502, detail="Failed to create Fault vertex")

    # 2. 确保 Solution 顶点存在
    sid = _upsert_vertex("Solution", payload.solution_name, {
        "description": payload.solution_description,
        "steps":       payload.steps,
        "data_source": payload.data_source,
        "confidence":  payload.confidence,
    })
    if not sid:
        raise HTTPException(status_code=502, detail="Failed to create Solution vertex")

    # 3. 检查边是否已存在，不存在则创建
    check = execute_gremlin(
        "g.V(fid).outE('HAS_SOLUTION').where(__.inV().hasId(sid)).count()",
        {"fid": fid, "sid": sid},
    )
    cnt = (_extract_data(check) or [0])[0]
    edge_status = "exists" if cnt > 0 else "created"
    if cnt == 0:
        execute_gremlin(
            "def fv = g.V(fid).next(); def sv = g.V(sid).next(); g.addE('HAS_SOLUTION').from(fv).to(sv).iterate()",
            {"fid": fid, "sid": sid},
        )

    def _bg_sync_fault_vector() -> None:
        try:
            _vec.upsert_fault_vector_for_name(execute_gremlin, _extract_data, payload.fault_name)
        except Exception:
            pass

    background_tasks.add_task(_bg_sync_fault_vector)
    return {"status": "ok", "edge_status": edge_status}


@app.get("/graph/faults")
def list_faults() -> Dict[str, Any]:
    result = execute_gremlin("g.V().hasLabel('Fault').values('name').order()")
    faults = _extract_data(result)
    return {"faults": faults, "count": len(faults)}


@app.get("/graph/query")
def query_solutions(fault_name: str) -> Dict[str, Any]:
    if not fault_name.strip():
        raise HTTPException(status_code=400, detail="fault_name cannot be empty")
    script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('HAS_SOLUTION').
  project('id', 'name', 'description', 'data_source', 'confidence').
    by(id()).by(values('name')).
    by(coalesce(values('description'), constant(''))).
    by(coalesce(values('data_source'), constant('unknown'))).
    by(coalesce(values('confidence'), constant(1.0)))
"""
    result = execute_gremlin(script, {"fault_name": fault_name})
    rows = _extract_data(result)
    return {"fault_name": fault_name, "solutions": rows, "count": len(rows)}


@app.get("/graph/visualize")
def visualize_graph(fault_name: str) -> Dict[str, Any]:
    if not fault_name.strip():
        raise HTTPException(status_code=400, detail="fault_name cannot be empty")
    nodes_script = """
g.V().hasLabel('Fault').has('name', fault_name).as('f').
  union(
    select('f').project('id','label','type').by(id()).by(values('name')).by(constant('Fault')),
    out('HAS_SOLUTION').project('id','label','type').by(id()).by(values('name')).by(constant('Solution'))
  )
"""
    edges_script = """
g.V().hasLabel('Fault').has('name', fault_name).
  outE('HAS_SOLUTION').
  project('id','source','target','label').
    by(id()).by(outV().id()).by(inV().id()).by(label())
"""
    nodes = _extract_data(execute_gremlin(nodes_script, {"fault_name": fault_name}))
    edges = _extract_data(execute_gremlin(edges_script, {"fault_name": fault_name}))
    return {"fault_name": fault_name, "nodes": nodes, "edges": edges,
            "node_count": len(nodes), "edge_count": len(edges)}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — Graph-RAG 上下文 & 相似推荐
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/graph/context")
def graph_context(fault_name: str) -> Dict[str, Any]:
    """
    Graph-RAG 上下文摘要接口，供 Dify 工作流 HTTP 节点调用。
    返回结构化的图谱摘要文本，直接拼入 LLM Prompt。
    """
    if not fault_name.strip():
        raise HTTPException(status_code=400, detail="fault_name cannot be empty")

    solutions_script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('HAS_SOLUTION').
  project('name','description','data_source','confidence').
    by(values('name')).
    by(coalesce(values('description'), constant(''))).
    by(coalesce(values('data_source'), constant('unknown'))).
    by(coalesce(values('confidence'), constant(1.0)))
"""
    sop_script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('HAS_SOP').
  project('title','steps','version').
    by(values('title')).
    by(coalesce(values('steps'), constant('[]'))).
    by(coalesce(values('version'), constant('1.0')))
"""
    category_script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('CLASSIFIED_AS').
  project('code','name','level','domain').
    by(values('code')).by(values('name')).
    by(coalesce(values('level'), constant(''))).
    by(coalesce(values('domain'), constant('')))
"""

    solutions = _extract_data(execute_gremlin(solutions_script, {"fault_name": fault_name}))
    sops      = _extract_data(execute_gremlin(sop_script,       {"fault_name": fault_name}))
    categories = _extract_data(execute_gremlin(category_script, {"fault_name": fault_name}))

    # 生成结构化摘要文本
    lines = [f"【图谱知识】故障名称：{fault_name}"]

    if categories:
        c = categories[0]
        lines.append(f"分类：{c.get('name','')}（{c.get('level','')} / {c.get('domain','')}）")

    if solutions:
        lines.append(f"已有 {len(solutions)} 条解决方案：")
        for i, s in enumerate(solutions[:5], 1):
            src = s.get("data_source", "unknown")
            conf = s.get("confidence", 1.0)
            lines.append(f"  {i}. {s['name']}（来源：{src}，置信度：{conf:.1f}）")
            if s.get("description"):
                lines.append(f"     {s['description'][:200]}")
    else:
        lines.append("暂无已录入的解决方案。")

    if sops:
        lines.append(f"关联 SOP：{sops[0]['title']}（版本 {sops[0]['version']}）")

    summary_text = "\n".join(lines)

    return {
        "fault_name":    fault_name,
        "solutions":     solutions,
        "sops":          sops,
        "categories":    categories,
        "summary_text":  summary_text,   # 直接拼入 LLM Prompt 的摘要
    }


def _keyword_fault_scores(query_lower: str, all_faults: List[str]) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []
    for fname in all_faults:
        score = 0.0
        fname_lower = fname.lower()
        if query_lower in fname_lower or fname_lower in query_lower:
            score = 0.9
        else:
            q_words = set(query_lower.replace("，", " ").replace(",", " ").split())
            f_words = set(fname_lower.replace("，", " ").replace(",", " ").split())
            intersection = q_words & f_words
            if intersection:
                score = len(intersection) / max(len(q_words), len(f_words))
        if score > 0:
            scored.append({"fault_name": fname, "similarity": round(score, 3)})
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored


def _recommendations_payload(top: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recommendations: List[Dict[str, Any]] = []
    for item in top:
        sol_result = execute_gremlin(
            "g.V().hasLabel('Fault').has('name', fault_name).out('HAS_SOLUTION')"
            ".project('name','description').by(values('name')).by(coalesce(values('description'), constant('')))",
            {"fault_name": item["fault_name"]},
        )
        solutions = _extract_data(sol_result)

        sop_result = execute_gremlin(
            "g.V().hasLabel('Fault').has('name', fault_name).out('HAS_SOP').values('title')",
            {"fault_name": item["fault_name"]},
        )
        sop_titles = _extract_data(sop_result)

        recommendations.append({
            "fault_name": item["fault_name"],
            "similarity": item["similarity"],
            "solutions":  solutions,
            "sop_titles": sop_titles,
        })
    return recommendations


@app.post("/graph/recommend")
def recommend_faults(payload: RecommendRequest) -> Dict[str, Any]:
    """
    相似故障推荐：优先 Qdrant 向量检索（需先 POST /admin/fault-vectors/sync）；
    无索引或未配置 embedding 时降级为关键词匹配。
    """
    query_lower = payload.query.lower()
    all_faults_result = execute_gremlin("g.V().hasLabel('Fault').values('name').order()")
    all_faults: List[str] = _extract_data(all_faults_result)

    method = "keyword"
    top: List[Dict[str, Any]] = []

    if _vec.embedding_configured() and _vec.qdrant_collection_point_count() > 0:
        vec_hits = _vec.search_similar_faults(payload.query, payload.top_k)
        if vec_hits:
            method = "vector"
            top = [{"fault_name": fn, "similarity": round(sc, 4)} for fn, sc in vec_hits]

    if not top:
        method = "keyword" if method == "keyword" else "keyword_fallback"
        kw = _keyword_fault_scores(query_lower, all_faults)
        top = kw[: payload.top_k]

    recommendations = _recommendations_payload(top)

    return {
        "query":           payload.query,
        "method":          method,
        "recommendations": recommendations,
        "total":           len(recommendations),
    }


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — SOP 管理
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/graph/sop")
def create_or_update_sop(payload: SOPRequest) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    steps_json = json.dumps(payload.steps, ensure_ascii=False)

    sop_script = """
def sop = g.V().hasLabel('SOP').has('title', title).fold().
      coalesce(__.unfold(),
               __.addV('SOP').property('title', title)
                             .property('version', ver)
                             .property('author', author)
                             .property('data_source', data_source)
                             .property('created_at', ts)).next()
sop.property('steps', steps)
sop.property('version', ver)
sop.id()
"""
    result = execute_gremlin(sop_script, {
        "title":       payload.title,
        "steps":       steps_json,
        "ver":         payload.version,
        "author":      payload.author,
        "data_source": payload.data_source,
        "ts":          now,
    })
    sop_ids = _extract_data(result)

    # 关联到 Fault
    if sop_ids:
        link_script = """
def f = g.V().hasLabel('Fault').has('name', fault_name).fold().
      coalesce(__.unfold(),
               __.addV('Fault').property('name', fault_name)
                               .property('data_source', 'manual')
                               .property('created_at', ts)).next()
def s = g.V().hasLabel('SOP').has('title', title).next()
if (!g.V(f).out('HAS_SOP').hasLabel('SOP').has('title', title).hasNext()) {
  g.V(f).as('a').V(s).addE('HAS_SOP').from('a').next()
  'linked'
} else {
  'already_linked'
}
"""
        execute_gremlin(link_script, {
            "fault_name": payload.fault_name,
            "title":      payload.title,
            "ts":         now,
        })

    return {"status": "ok", "title": payload.title, "fault_name": payload.fault_name}


@app.get("/graph/sop")
def list_sops(fault_name: Optional[str] = None) -> Dict[str, Any]:
    try:
        if fault_name:
            script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('HAS_SOP').
  project('title','steps','version','author','data_source').
    by(values('title')).
    by(coalesce(values('steps'), constant('[]'))).
    by(coalesce(values('version'), constant('1.0'))).
    by(coalesce(values('author'), constant(''))).
    by(coalesce(values('data_source'), constant('manual')))
"""
            result = execute_gremlin(script, {"fault_name": fault_name})
        else:
            script = """
g.V().hasLabel('SOP').
  project('title','steps','version','author','data_source').
    by(values('title')).
    by(coalesce(values('steps'), constant('[]'))).
    by(coalesce(values('version'), constant('1.0'))).
    by(coalesce(values('author'), constant(''))).
    by(coalesce(values('data_source'), constant('manual')))
"""
            result = execute_gremlin(script)

        sops = _extract_data(result)
        for sop in sops:
            if isinstance(sop.get("steps"), str):
                try:
                    sop["steps"] = json.loads(sop["steps"])
                except Exception:
                    sop["steps"] = []
        return {"sops": sops, "count": len(sops)}
    except HTTPException:
        # SOP 顶点标签尚未创建时返回空列表，不报错
        return {"sops": [], "count": 0}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — 资产管理
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/assets/sync")
def sync_assets(assets: List[AssetRequest]) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    success, failed = 0, 0
    for asset in assets:
        try:
            script = """
g.V().hasLabel('Asset').has('asset_id', aid).fold().
  coalesce(__.unfold()
              .property('name', aname)
              .property('asset_type', atype)
              .property('ip', ip)
              .property('env', env)
              .property('data_source', data_source),
           __.addV('Asset').property('asset_id', aid)
                           .property('name', aname)
                           .property('asset_type', atype)
                           .property('ip', ip)
                           .property('env', env)
                           .property('data_source', data_source)
                           .property('created_at', ts)).next()
'ok'
"""
            execute_gremlin(script, {
                "aid": asset.asset_id, "aname": asset.name,
                "atype": asset.asset_type, "ip": asset.ip,
                "env": asset.env, "data_source": asset.data_source,
                "ts": now,
            })
            success += 1
        except Exception:
            failed += 1
    return {"status": "ok", "success": success, "failed": failed, "total": len(assets)}


@app.get("/assets")
def list_assets(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    script = """
g.V().hasLabel('Asset').range(offset, offset + limit).
  project('asset_id','name','asset_type','ip','env','data_source').
    by(values('asset_id')).by(coalesce(values('name'), constant(''))).
    by(coalesce(values('asset_type'), constant('server'))).
    by(coalesce(values('ip'), constant(''))).
    by(coalesce(values('env'), constant('prod'))).
    by(coalesce(values('data_source'), constant('manual')))
"""
    result = execute_gremlin(script, {"offset": offset, "limit": page_size})
    assets = _extract_data(result)
    total_result = execute_gremlin("g.V().hasLabel('Asset').count()")
    total = (_extract_data(total_result) or [0])[0]
    return {"assets": assets, "page": page, "page_size": page_size, "total": total}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — 告警接入
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/alerts/ingest")
def ingest_alert(payload: AlertIngestRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    occurred = payload.occurred_at or now
    script = """
def al = g.V().hasLabel('Alert').has('alert_id', alert_id).fold().
      coalesce(__.unfold(),
               __.addV('Alert').property('alert_id', alert_id)
                               .property('content', content)
                               .property('level', level)
                               .property('source', source)
                               .property('occurred_at', occurred)
                               .property('data_source', data_source)).next()
if (asset_id != '') {
  def ast = g.V().hasLabel('Asset').has('asset_id', asset_id).fold().next()
  if (!ast.isEmpty()) {
    def a = ast.get(0)
    if (!g.V(a).out('HAS_ALERT').hasLabel('Alert').has('alert_id', alert_id).hasNext()) {
      g.V(a).as('x').V(al).addE('HAS_ALERT').property('created_at', ts).from('x').next()
    }
  }
}
al.id()
"""
    result = execute_gremlin(script, {
        "alert_id":   payload.alert_id,
        "content":    payload.content,
        "level":      payload.level,
        "source":     payload.source,
        "occurred":   occurred,
        "data_source": payload.data_source,
        "asset_id":   payload.asset_id,
        "ts":         now,
    })
    return {"status": "ok", "alert_id": payload.alert_id}


@app.get("/alerts")
def list_alerts(asset_id: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    if asset_id:
        script = """
g.V().hasLabel('Asset').has('asset_id', asset_id).
  out('HAS_ALERT').range(offset, offset + limit).
  project('alert_id','content','level','source','occurred_at').
    by(values('alert_id')).by(values('content')).
    by(values('level')).by(values('source')).
    by(coalesce(values('occurred_at'), constant(0)))
"""
        result = execute_gremlin(script, {"asset_id": asset_id, "offset": offset, "limit": page_size})
    else:
        script = """
g.V().hasLabel('Alert').order().by('occurred_at', decr).range(offset, offset + limit).
  project('alert_id','content','level','source','occurred_at').
    by(values('alert_id')).by(values('content')).
    by(values('level')).by(values('source')).
    by(coalesce(values('occurred_at'), constant(0)))
"""
        result = execute_gremlin(script, {"offset": offset, "limit": page_size})
    alerts = _extract_data(result)
    return {"alerts": alerts, "page": page, "page_size": page_size}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — 工单 / Incident
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/incidents")
def create_incident(payload: IncidentRequest) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    script = """
def inc = g.V().hasLabel('Incident').has('incident_id', incident_id).fold().
      coalesce(__.unfold(),
               __.addV('Incident').property('incident_id', incident_id)
                                  .property('title', title)
                                  .property('status', 'closed')
                                  .property('mttr_minutes', mttr)
                                  .property('data_source', data_source)
                                  .property('created_at', ts)
                                  .property('closed_at', ts)).next()
'ok'
"""
    execute_gremlin(script, {
        "incident_id": payload.incident_id,
        "title":       payload.title,
        "mttr":        payload.mttr_minutes,
        "data_source": payload.data_source,
        "ts":          now,
    })

    # 关联 Fault
    if payload.fault_name:
        _link_incident_fault(payload.incident_id, payload.fault_name, now)
    # 关联 Solution
    if payload.solution_name:
        _link_incident_solution(payload.incident_id, payload.solution_name, now)
    # 关联 Asset
    if payload.asset_id:
        _link_incident_asset(payload.incident_id, payload.asset_id)

    return {"status": "ok", "incident_id": payload.incident_id}


def _link_incident_fault(incident_id: str, fault_name: str, ts: int) -> None:
    script = """
def inc = g.V().hasLabel('Incident').has('incident_id', incident_id).next()
def f = g.V().hasLabel('Fault').has('name', fault_name).fold().next()
if (!f.isEmpty() && !g.V(inc).out('CAUSED_BY').hasLabel('Fault').has('name', fault_name).hasNext()) {
  g.V(inc).as('a').V(f.get(0)).addE('CAUSED_BY').from('a').next()
}
'done'
"""
    try:
        execute_gremlin(script, {"incident_id": incident_id, "fault_name": fault_name, "ts": ts})
    except Exception:
        pass


def _link_incident_solution(incident_id: str, solution_name: str, ts: int) -> None:
    script = """
def inc = g.V().hasLabel('Incident').has('incident_id', incident_id).next()
def s = g.V().hasLabel('Solution').has('name', solution_name).fold().next()
if (!s.isEmpty() && !g.V(inc).out('RESOLVED_BY').hasLabel('Solution').has('name', solution_name).hasNext()) {
  g.V(inc).as('a').V(s.get(0)).addE('RESOLVED_BY').property('adopted_at', ts).from('a').next()
}
'done'
"""
    try:
        execute_gremlin(script, {"incident_id": incident_id, "solution_name": solution_name, "ts": ts})
    except Exception:
        pass


def _link_incident_asset(incident_id: str, asset_id: str) -> None:
    script = """
def inc = g.V().hasLabel('Incident').has('incident_id', incident_id).next()
def a = g.V().hasLabel('Asset').has('asset_id', asset_id).fold().next()
if (!a.isEmpty() && !g.V(inc).out('INVOLVES').hasLabel('Asset').has('asset_id', asset_id).hasNext()) {
  g.V(inc).as('x').V(a.get(0)).addE('INVOLVES').property('role', 'affected').from('x').next()
}
'done'
"""
    try:
        execute_gremlin(script, {"incident_id": incident_id, "asset_id": asset_id})
    except Exception:
        pass


@app.get("/incidents")
def list_incidents(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    script = """
g.V().hasLabel('Incident').order().by('created_at', decr).range(offset, offset + limit).
  project('incident_id','title','status','mttr_minutes','created_at','data_source').
    by(values('incident_id')).by(values('title')).
    by(coalesce(values('status'), constant('closed'))).
    by(coalesce(values('mttr_minutes'), constant(0))).
    by(coalesce(values('created_at'), constant(0))).
    by(coalesce(values('data_source'), constant('manual')))
"""
    result = execute_gremlin(script, {"offset": offset, "limit": page_size})
    incidents = _extract_data(result)
    return {"incidents": incidents, "page": page, "page_size": page_size}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — 知识抽取队列
# ──────────────────────────────────────────────────────────────────────────────

def _llm_extract(text: str, job_id: str, source_hint: str) -> None:
    """后台异步抽取任务（调用 LLM 或规则降级）"""
    _extract_jobs[job_id]["status"] = "running"
    candidates: List[Dict[str, Any]] = []

    if LLM_API_URL and LLM_API_KEY:
        try:
            prompt = f"""你是一名 IT 运维知识工程师。请从以下文本中提取故障–解决方案关系，
以 JSON 数组输出，每项包含：
  fault_name（字符串）
  solution_name（字符串）
  solution_description（字符串，不超过500字）
  confidence（0.0~1.0）

文本：
{text[:3000]}

仅输出 JSON 数组，不要其他内容。"""

            resp = requests.post(
                LLM_API_URL,
                headers={"Authorization": f"Bearer {LLM_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": LLM_CHAT_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.1},
                timeout=60,
            )
            if resp.ok:
                content = resp.json()["choices"][0]["message"]["content"]
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    candidates = json.loads(content[start:end])
        except Exception as e:
            _extract_jobs[job_id]["error"] = str(e)
    else:
        # 规则降级：逐行解析简单格式
        for line in text.split("\n"):
            line = line.strip()
            if "故障" in line and ("解决" in line or "方案" in line or "处理" in line):
                candidates.append({
                    "fault_name": line[:50],
                    "solution_name": "待补充",
                    "solution_description": line,
                    "confidence": 0.5,
                })

    # 写入审核队列
    for c in candidates:
        qid = str(uuid.uuid4())[:8]
        _extract_queue[qid] = {
            "id":          qid,
            "job_id":      job_id,
            "source_hint": source_hint,
            "fault_name":           c.get("fault_name", ""),
            "solution_name":        c.get("solution_name", ""),
            "solution_description": c.get("solution_description", ""),
            "confidence":           c.get("confidence", 0.7),
            "status":      "pending",
            "created_at":  int(time.time() * 1000),
        }

    _extract_jobs[job_id]["status"] = "done"
    _extract_jobs[job_id]["candidate_count"] = len(candidates)


@app.post("/extract/submit")
def extract_submit(payload: ExtractSubmitRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())[:12]
    _extract_jobs[job_id] = {
        "job_id":      job_id,
        "source_hint": payload.source_hint,
        "status":      "pending",
        "created_at":  int(time.time() * 1000),
        "candidate_count": 0,
    }
    background_tasks.add_task(_llm_extract, payload.text, job_id, payload.source_hint)
    return {"status": "ok", "job_id": job_id, "message": "抽取任务已提交，请稍后查看队列"}


@app.get("/extract/jobs")
def list_extract_jobs() -> Dict[str, Any]:
    jobs = sorted(_extract_jobs.values(), key=lambda x: x["created_at"], reverse=True)
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/extract/queue")
def list_extract_queue(status: str = "pending") -> Dict[str, Any]:
    items = [v for v in _extract_queue.values() if v["status"] == status]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"items": items, "total": len(items)}


@app.post("/extract/queue/{item_id}/approve")
def approve_extract(item_id: str) -> Dict[str, Any]:
    if item_id not in _extract_queue:
        raise HTTPException(status_code=404, detail="item not found")
    item = _extract_queue[item_id]
    if item["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"item status is {item['status']}, not pending")

    # 写入图谱
    req = AddRelationRequest(
        fault_name=item["fault_name"],
        solution_name=item["solution_name"],
        solution_description=item["solution_description"],
        data_source="extracted_approved",
        confidence=item.get("confidence", 0.8),
        import_batch_id=f"extract-{item['job_id']}",
    )
    add_relation(req)
    item["status"] = "approved"
    return {"status": "ok", "item_id": item_id, "message": "已写入图谱"}


@app.post("/extract/queue/{item_id}/reject")
def reject_extract(item_id: str) -> Dict[str, Any]:
    if item_id not in _extract_queue:
        raise HTTPException(status_code=404, detail="item not found")
    _extract_queue[item_id]["status"] = "rejected"
    return {"status": "ok", "item_id": item_id}


# ──────────────────────────────────────────────────────────────────────────────
# V2.0 — 运营统计
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/ops/stats")
def ops_stats() -> Dict[str, Any]:
    def _safe_count(label: str) -> int:
        try:
            r = execute_gremlin(f"g.V().hasLabel('{label}').count()")
            return (_extract_data(r) or [0])[0]
        except Exception:
            return 0

    fault_count     = _safe_count("Fault")
    solution_count  = _safe_count("Solution")
    sop_count       = _safe_count("SOP")
    asset_count     = _safe_count("Asset")
    incident_count  = _safe_count("Incident")
    alert_count     = _safe_count("Alert")
    category_count  = _safe_count("Category")

    # 知识覆盖率：有 Solution 的 Fault / 总 Fault
    # HugeGraph 兼容写法：先查 HAS_SOLUTION 边的起点 id 集合，再计数
    covered = 0
    try:
        covered_result = execute_gremlin(
            "g.E().hasLabel('HAS_SOLUTION').outV().hasLabel('Fault').dedup().count()"
        )
        covered = (_extract_data(covered_result) or [0])[0]
    except Exception:
        covered = 0
    coverage_rate = round(covered / fault_count * 100, 1) if fault_count > 0 else 0.0

    # Fault 按 data_source 分布：按图中实际取值计数（兼容 gaia、open_gaia 等），并单独统计未设属性
    source_dist: Dict[str, int] = {}
    try:
        distinct_src = _extract_data(
            execute_gremlin("g.V().hasLabel('Fault').values('data_source').dedup()")
        )
        for src in distinct_src or []:
            if src is None:
                continue
            r = execute_gremlin(
                "g.V().hasLabel('Fault').has('data_source', ds).count()",
                {"ds": src},
            )
            cnt = int((_extract_data(r) or [0])[0])
            if cnt <= 0:
                continue
            key = "unset" if str(src).strip() == "" else str(src)
            source_dist[key] = source_dist.get(key, 0) + cnt
        r_nop = execute_gremlin(
            "g.V().hasLabel('Fault').not(__.has('data_source')).count()"
        )
        no_prop = int((_extract_data(r_nop) or [0])[0])
        if no_prop > 0:
            source_dist["unset"] = source_dist.get("unset", 0) + no_prop
    except Exception:
        source_dist = {}

    def _edge_cnt(lbl: str) -> int:
        try:
            r = execute_gremlin(f"g.E().hasLabel('{lbl}').count()")
            return int((_extract_data(r) or [0])[0])
        except Exception:
            return 0

    # 方案复用率
    resolved = 0
    try:
        resolved_result = execute_gremlin(
            "g.E().hasLabel('RESOLVED_BY').outV().hasLabel('Incident').dedup().count()"
        )
        resolved = (_extract_data(resolved_result) or [0])[0]
    except Exception:
        resolved = 0
    reuse_rate = round(resolved / incident_count * 100, 1) if incident_count > 0 else 0.0

    # 抽取转化率
    approved = sum(1 for v in _extract_queue.values() if v["status"] == "approved")
    total_q  = len(_extract_queue)
    extract_rate = round(approved / total_q * 100, 1) if total_q > 0 else 0.0

    return {
        "node_counts": {
            "Fault":     fault_count,
            "Solution":  solution_count,
            "SOP":       sop_count,
            "Asset":     asset_count,
            "Incident":  incident_count,
            "Alert":     alert_count,
            "Category":  category_count,
        },
        "coverage_rate":   coverage_rate,
        "reuse_rate":      reuse_rate,
        "extract_rate":    extract_rate,
        "source_distribution": source_dist,
        "edge_counts": {
            "TRIGGERS":     _edge_cnt("TRIGGERS"),
            "CLASSIFIED_AS": _edge_cnt("CLASSIFIED_AS"),
            "HAS_SOLUTION": _edge_cnt("HAS_SOLUTION"),
            "HAS_ALERT":    _edge_cnt("HAS_ALERT"),
        },
        "extract_queue": {
            "total":    total_q,
            "pending":  sum(1 for v in _extract_queue.values() if v["status"] == "pending"),
            "approved": approved,
            "rejected": sum(1 for v in _extract_queue.values() if v["status"] == "rejected"),
        },
    }


@app.get("/ops/stats/growth")
def ops_growth(window: str = "week") -> Dict[str, Any]:
    """节点增长趋势（按时间窗口）"""
    now = int(time.time() * 1000)
    if window == "week":
        since = now - 7 * 24 * 3600 * 1000
    elif window == "month":
        since = now - 30 * 24 * 3600 * 1000
    else:
        since = 0

    def _count_since(label: str) -> int:
        try:
            # HugeGraph 兼容：使用 P.gte 谓词
            r = execute_gremlin(
                f"g.V().hasLabel('{label}').has('created_at', P.gte(ts)).count()",
                {"ts": since}
            )
            return (_extract_data(r) or [0])[0]
        except Exception:
            # 降级：返回总数（不支持 created_at 过滤时）
            try:
                r = execute_gremlin(f"g.V().hasLabel('{label}').count()")
                return (_extract_data(r) or [0])[0]
            except Exception:
                return 0

    return {
        "window":   window,
        "since_ms": since,
        "new_nodes": {
            "Fault":    _count_since("Fault"),
            "Solution": _count_since("Solution"),
            "SOP":      _count_since("SOP"),
        }
    }
