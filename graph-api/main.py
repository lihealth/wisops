"""WisOps Graph API — 平台 V1.9（图谱 Schema V2.0）"""
import json
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import requests
import vector_search as _vec
from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="WisOps Graph API",
    version="1.9.0",
    root_path="/graph-api",
    root_path_in_servers=False,
)

HUGEGRAPH_URL   = os.getenv("HUGEGRAPH_URL",   "http://localhost:8081").rstrip("/")
HUGEGRAPH_GRAPH = os.getenv("HUGEGRAPH_GRAPH", "hugegraph")
LLM_API_URL     = os.getenv("LLM_API_URL",     "")
LLM_API_KEY     = os.getenv("LLM_API_KEY",     "")
LLM_CHAT_MODEL  = os.getenv("LLM_CHAT_MODEL", "gpt-4o-mini")
DIFY_DATASET_API_URL = os.getenv("DIFY_DATASET_API_URL", "").rstrip("/")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID", "")
DIFY_DATASET_API_KEY = os.getenv("DIFY_DATASET_API_KEY", "")
REQUEST_TIMEOUT = 10

# ── SEC：API Key 校验 ──────────────────────────────────────────────────────────
# 设置 GRAPH_API_KEY 环境变量后，所有写操作（POST/PUT/DELETE）需在请求头传入：
#   X-API-Key: <your-key>
# 未设置时跳过校验（开发/本地模式），日志会输出警告。
GRAPH_API_KEY: str = os.getenv("GRAPH_API_KEY", "").strip()

# 不需要 Key 的读路径白名单（GET 请求默认不鉴权，此处仅供扩展）
_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
# 部分 POST 路径允许匿名（健康检查等），按前缀匹配
_AUTH_EXEMPT_PREFIXES = (
    "/graph-api/health",
    "/graph-api/docs",
    "/graph-api/openapi",
    "/graph-api/redoc",
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if GRAPH_API_KEY and request.method in _WRITE_METHODS:
        path = request.url.path
        exempt = any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES)
        if not exempt:
            provided = request.headers.get("X-API-Key", "").strip()
            if provided != GRAPH_API_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing X-API-Key header"},
                )
    response = await call_next(request)
    return response


# ── SEC：写操作审计日志 ────────────────────────────────────────────────────────
# 格式：{timestamp_ms, method, path, status_code, user_hint, elapsed_ms}
# 内存存储（重启丢失），最多保留 AUDIT_MAX_ENTRIES 条，超出时滚动丢弃最旧的。
AUDIT_MAX_ENTRIES: int = int(os.getenv("AUDIT_MAX_ENTRIES", "2000"))
_audit_log: List[Dict[str, Any]] = []


def _audit(method: str, path: str, status_code: int, user_hint: str, elapsed_ms: int) -> None:
    entry = {
        "timestamp_ms": int(time.time() * 1000),
        "method":       method,
        "path":         path,
        "status_code":  status_code,
        "user_hint":    user_hint,
        "elapsed_ms":   elapsed_ms,
    }
    _audit_log.append(entry)
    if len(_audit_log) > AUDIT_MAX_ENTRIES:
        del _audit_log[:len(_audit_log) - AUDIT_MAX_ENTRIES]


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """记录所有写操作的入参概要与响应状态。"""
    if request.method not in _WRITE_METHODS:
        return await call_next(request)
    path = request.url.path
    exempt = any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES)
    if exempt:
        return await call_next(request)
    t0 = time.monotonic()
    response = await call_next(request)
    elapsed = int((time.monotonic() - t0) * 1000)
    user_hint = request.headers.get("X-User", request.headers.get("X-API-Key", "anonymous")[:16])
    _audit(request.method, path, response.status_code, user_hint, elapsed)
    return response


_ACTIVE_GREMLIN_ENDPOINT: Optional[str] = None

# 内存审核队列（生产可替换为 Redis/DB）
_extract_queue: Dict[str, Dict[str, Any]] = {}
# 抽取任务状态
_extract_jobs: Dict[str, Dict[str, Any]] = {}
# 已审核知识与 Dify 文档关联索引（内存态，重启丢失；后续可迁移 DB）
_extract_doc_links: List[Dict[str, Any]] = []


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

class ExtractBatchIdsRequest(BaseModel):
    """批量审核：单次最多 50 条，避免长时间阻塞 HTTP。"""
    item_ids: List[str] = Field(..., min_length=1, max_length=50)

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


# HugeGraph Gremlin HTTP 单次返回条数有上限（Gremlin Server 迭代批量默认约 64），
# 未使用 range 分页时，一次遍历只能拿到「前几十条」。
GREMLIN_RANGE_PAGE = 500


def _gremlin_collect_paged(script_for_range: Callable[[int, int], str]) -> List[Any]:
    """按固定步长 range(low,high) 分页执行 Gremlin，合并为完整列表。"""
    aggregated: List[Any] = []
    offset = 0
    while True:
        script = script_for_range(offset, offset + GREMLIN_RANGE_PAGE)
        chunk = _extract_data(execute_gremlin(script))
        if not chunk:
            break
        aggregated.extend(chunk)
        if len(chunk) < GREMLIN_RANGE_PAGE:
            break
        offset += GREMLIN_RANGE_PAGE
    return aggregated


def _all_fault_names_ordered() -> List[str]:
    # 启动时 HugeGraph 若未就绪，startup 里 ensure_schema_v2 可能被静默跳过；
    # 首次拉取 Fault 名单前再幂等执行一次，避免 Undefined vertex label: 'Fault'
    ensure_schema_v2()
    rows = _gremlin_collect_paged(
        lambda lo, hi: (
            f"g.V().hasLabel('Fault').order().by('name').range({lo}, {hi}).values('name')"
        ),
    )
    return [str(x) for x in rows]


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
schema.propertyKey('rule_name').asText().ifNotExist().create()
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
  schema.edgeLabel('TRIGGERS').sourceLabel('Alert').targetLabel('Fault').properties('created_at','confidence','method','rule_name').nullableKeys('created_at','confidence','method','rule_name').create()
} else {
  schema.edgeLabel('TRIGGERS').properties('confidence','method','rule_name').nullableKeys('confidence','method','rule_name').append()
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


# ── SEC：审计日志查询 ──────────────────────────────────────────────────────────

@app.get("/admin/audit-log")
def get_audit_log(
    limit:   int = Query(100, ge=1, le=1000),
    method:  str = Query("", description="过滤 HTTP 方法，如 POST"),
    path_kw: str = Query("", description="路径关键词过滤（子串匹配）"),
) -> Dict[str, Any]:
    """
    返回最近写操作审计记录（内存态，重启丢失）。
    按时间倒序，limit 最多 1000 条。
    """
    rows = list(reversed(_audit_log))
    if method.strip():
        rows = [r for r in rows if r["method"].upper() == method.strip().upper()]
    if path_kw.strip():
        kw = path_kw.strip().lower()
        rows = [r for r in rows if kw in r["path"].lower()]
    return {
        "total":   len(_audit_log),
        "returned": min(len(rows), limit),
        "items":   rows[:limit],
    }


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
    fault_rows = _gremlin_collect_paged(
        lambda lo, hi: (
            "g.V().hasLabel('Fault').order().by('name')"
            f".range({lo}, {hi}).project('vid','dom')"
            ".by(id()).by(coalesce(values('domain'), constant('')))"
        ),
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
    # 告警文本中提取可判别 token，过滤通用词，降低“全量误匹配”
    stop_words = {
        "service", "trigger", "anomalies", "anomaly", "error", "warning",
        "host", "node", "system", "application", "cluster", "parallel",
        "fast", "sort", "normal", "metric", "event",
    }
    content_tokens = {
        t for t in re.findall(r"[a-z_]{4,}", c)
        if t not in stop_words
    }
    base = re.sub(r"[（(][^)）]*[)）]", "", fault_name).strip().lower()
    fault_tokens = {
        t for t in re.findall(r"[a-z_]{4,}", fault_name.lower())
        if t not in stop_words
    }

    # 若几乎没有 token 交集，直接判不匹配（避免把所有 alert 都连到任意 fault）
    if content_tokens and fault_tokens and not (content_tokens & fault_tokens):
        return 0.0

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


_ALERT_FAULT_RULES = [
    {
        # GAIA: memory_anomalies + dbservice
        "pattern": re.compile(r"\[memory_anomalies\]|memory_anomalies", re.I),
        "content_keywords": ["dbservice", "mysql", "database", "db "],
        "fault_keywords": ["mysql", "database", "db", "connection"],
        "score": 0.95,
        "name": "gaia-memory-db",
    },
    {
        # GAIA: memory_anomalies + redisservice
        "pattern": re.compile(r"\[memory_anomalies\]|memory_anomalies", re.I),
        "content_keywords": ["redisservice", "redis"],
        "fault_keywords": ["redis", "replication", "cache"],
        "score": 0.95,
        "name": "gaia-memory-redis",
    },
    {
        # GAIA: memory_anomalies + webservice
        "pattern": re.compile(r"\[memory_anomalies\]|memory_anomalies", re.I),
        "content_keywords": ["webservice", "nginx", "apache", "http"],
        "fault_keywords": ["nginx", "apache", "web", "http"],
        "score": 0.94,
        "name": "gaia-memory-web",
    },
    {
        # GAIA: memory_anomalies + logservice
        "pattern": re.compile(r"\[memory_anomalies\]|memory_anomalies", re.I),
        "content_keywords": ["logservice", "elk", "elasticsearch"],
        "fault_keywords": ["elasticsearch", "log", "queue", "rejected"],
        "score": 0.94,
        "name": "gaia-memory-log",
    },
    {
        # GAIA: memory_anomalies + mobservice
        "pattern": re.compile(r"\[memory_anomalies\]|memory_anomalies", re.I),
        "content_keywords": ["mobservice", "k8s", "kubernetes"],
        "fault_keywords": ["k8s", "kubernetes", "memorypressure", "insufficient cpu/memory"],
        "score": 0.95,
        "name": "gaia-memory-mob",
    },
    {
        # GAIA 数据中主告警类型之一：cpu_anomalies + dbservice
        "pattern": re.compile(r"\[cpu_anomalies\]|cpu_anomalies", re.I),
        "content_keywords": ["dbservice", "mysql", "database", "db "],
        "fault_keywords": ["mysql", "database", "cpu", "high cpu"],
        "score": 0.93,
        "name": "gaia-cpu-db",
    },
    {
        # GAIA: cpu_anomalies + redisservice
        "pattern": re.compile(r"\[cpu_anomalies\]|cpu_anomalies", re.I),
        "content_keywords": ["redisservice", "redis"],
        "fault_keywords": ["redis", "cpu", "cache"],
        "score": 0.93,
        "name": "gaia-cpu-redis",
    },
    {
        # GAIA: cpu_anomalies + webservice
        "pattern": re.compile(r"\[cpu_anomalies\]|cpu_anomalies", re.I),
        "content_keywords": ["webservice", "nginx", "apache", "http"],
        "fault_keywords": ["nginx", "apache", "cpu", "web"],
        "score": 0.92,
        "name": "gaia-cpu-web",
    },
    {
        # GAIA: cpu_anomalies + mobservice / k8s
        "pattern": re.compile(r"\[cpu_anomalies\]|cpu_anomalies", re.I),
        "content_keywords": ["mobservice", "k8s", "kubernetes"],
        "fault_keywords": ["k8s", "kubernetes", "cpu", "insufficient cpu/memory"],
        "score": 0.94,
        "name": "gaia-cpu-mob",
    },
    {
        "pattern": re.compile(r"authentication failure|invalid user|pam_unix", re.I),
        "fault_keywords": ["ssh", "暴力", "破解", "authentication", "invalid user"],
        "score": 0.95,
        "name": "ssh-auth-failure",
    },
    {
        "pattern": re.compile(r"send worker leaving thread|connection broken for id", re.I),
        "fault_keywords": ["zookeeper", "peer", "连接中断", "sendworker"],
        "score": 0.9,
        "name": "zookeeper-peer-broken",
    },
    {
        "pattern": re.compile(r"mod_jk child workerenv in error state", re.I),
        "fault_keywords": ["apache", "mod_jk", "worker", "error state"],
        "score": 0.92,
        "name": "apache-modjk-error",
    },
    {
        "pattern": re.compile(r"got exception while serving blk_", re.I),
        "fault_keywords": ["hdfs", "datanode", "block", "blk_", "传输异常"],
        "score": 0.88,
        "name": "hdfs-block-serving-exception",
    },
]


def _rule_score_alert_fault_match(content: str, fault_name: str) -> tuple[float, str]:
    """
    规则优先匹配：返回 (score, rule_name)。
    若未命中，返回 (0.0, "")。
    """
    if not content or not fault_name:
        return 0.0, ""
    c = content.lower()
    f = fault_name.lower()
    best_score = 0.0
    best_rule = ""
    for rule in _ALERT_FAULT_RULES:
        if not rule["pattern"].search(c):
            continue
        # 若配置了 content_keywords，要求告警内容至少命中一个关键词
        content_keys = rule.get("content_keywords") or []
        if content_keys and not any(str(k).lower() in c for k in content_keys):
            continue
        # 规则命中后，再要求故障名至少含一个关键词，降低误匹配
        if not any(k in f for k in rule["fault_keywords"]):
            continue
        sc = float(rule["score"])
        if sc > best_score:
            best_score = sc
            best_rule = str(rule["name"])
    return best_score, best_rule


@app.post("/admin/triggers/sync")
def admin_triggers_sync(
    top_k_per_alert: int = 2,
    min_confidence: float = 0.72,
    dry_run: bool = False,
    include_candidates: bool = False,
    candidate_limit: int = 5000,
) -> Dict[str, Any]:
    """
    按告警文本与故障名匹配，批量补 TRIGGERS 边（幂等，已存在则跳过）。
    - 规则匹配优先（可追溯 rule_name）
    - 规则未命中时使用模糊打分兜底
    - dry_run=true 只统计不写边
    top_k_per_alert：每条告警最多关联几条故障（默认 2，最大 5）。
    min_confidence：最低置信阈值（0~1）。
    include_candidates：返回候选明细（用于审计导出）。
    candidate_limit：候选明细最大返回条数（默认 5000）。
    """
    ensure_schema_v2()
    now = int(time.time() * 1000)
    top_k = max(1, min(int(top_k_per_alert), 5))
    min_conf = max(0.0, min(float(min_confidence), 1.0))

    faults_raw = _gremlin_collect_paged(
        lambda lo, hi: (
            "g.V().hasLabel('Fault').order().by('name')"
            f".range({lo}, {hi}).project('vid','name').by(id()).by(values('name'))"
        ),
    )
    faults: List[Dict[str, str]] = []
    for row in faults_raw or []:
        if isinstance(row, dict) and row.get("vid") and row.get("name"):
            faults.append({"vid": str(row["vid"]), "name": str(row["name"])})

    alerts_raw = _gremlin_collect_paged(
        lambda lo, hi: (
            "g.V().hasLabel('Alert').order().by('alert_id')"
            f".range({lo}, {hi}).project('vid','c')"
            ".by(id()).by(coalesce(values('content'), constant('')))"
        ),
    )
    alerts: List[Dict[str, str]] = []
    for row in alerts_raw or []:
        if isinstance(row, dict) and row.get("vid"):
            alerts.append({"vid": str(row["vid"]), "c": str(row.get("c") or "")})

    created = 0
    skipped = 0
    matched_alerts = 0
    candidate_edges = 0
    rule_hits = 0
    fuzzy_hits = 0
    samples: List[Dict[str, Any]] = []
    candidate_rows: List[Dict[str, Any]] = []
    max_candidates = max(1, min(int(candidate_limit), 20000))

    for al in alerts:
        content = al["c"]
        scored: List[tuple] = []
        for f in faults:
            rule_sc, rule_name = _rule_score_alert_fault_match(content, f["name"])
            if rule_sc >= min_conf:
                scored.append((rule_sc, f["vid"], "rule", rule_name, f["name"]))
                continue
            fuzzy_sc = _score_alert_fault_match(content, f["name"])
            if fuzzy_sc >= min_conf:
                scored.append((fuzzy_sc, f["vid"], "fuzzy", "", f["name"]))
        scored.sort(key=lambda x: -x[0])
        chosen = scored[:top_k]
        if chosen:
            matched_alerts += 1
            candidate_edges += len(chosen)
            for _, _, method, _, _ in chosen:
                if method == "rule":
                    rule_hits += 1
                else:
                    fuzzy_hits += 1
        for sc, fvid, method, rule_name, fault_name in chosen:
            if len(samples) < 10:
                samples.append(
                    {
                        "alert_id": al["vid"],
                        "fault_id": fvid,
                        "fault_name": fault_name,
                        "confidence": round(float(sc), 3),
                        "method": method,
                        "rule_name": rule_name,
                    }
                )
            chk = execute_gremlin(
                "g.V(aid).outE('TRIGGERS').where(__.inV().hasId(fid)).count()",
                {"aid": al["vid"], "fid": fvid},
            )
            exists = (_extract_data(chk) or [0])[0] > 0
            if include_candidates and len(candidate_rows) < max_candidates:
                candidate_rows.append(
                    {
                        "alert_id": al["vid"],
                        "fault_id": fvid,
                        "fault_name": fault_name,
                        "confidence": round(float(sc), 3),
                        "method": method,
                        "rule_name": rule_name,
                        "exists": bool(exists),
                    }
                )
            if exists:
                # 已有关联边时补齐/刷新可追溯属性，便于审计
                if not dry_run:
                    try:
                        execute_gremlin(
                            "g.V(aid).outE('TRIGGERS').where(__.inV().hasId(fid))"
                            ".property('confidence', conf)"
                            ".property('method', mtd)"
                            ".property('rule_name', rname)"
                            ".iterate()",
                            {
                                "aid": al["vid"],
                                "fid": fvid,
                                "conf": float(sc),
                                "mtd": method,
                                "rname": rule_name or "",
                            },
                        )
                    except HTTPException:
                        pass
                skipped += 1
                continue
            if dry_run:
                continue
            try:
                execute_gremlin(
                    "def av = g.V(aid).next(); def fv = g.V(fid).next(); "
                    "g.addE('TRIGGERS').from(av).to(fv)"
                    ".property('created_at', ts)"
                    ".property('confidence', conf)"
                    ".property('method', mtd)"
                    ".property('rule_name', rname)"
                    ".iterate()",
                    {
                        "aid": al["vid"],
                        "fid": fvid,
                        "ts": now,
                        "conf": float(sc),
                        "mtd": method,
                        "rname": rule_name or "",
                    },
                )
                created += 1
            except HTTPException:
                pass

    return {
        "status":         "ok",
        "alerts_scanned": len(alerts),
        "faults_indexed": len(faults),
        "matched_alerts": matched_alerts,
        "candidate_edges": candidate_edges,
        "rule_hits": rule_hits,
        "fuzzy_hits": fuzzy_hits,
        "triggers_created": created,
        "triggers_skip_exists": skipped,
        "min_confidence": min_conf,
        "top_k_per_alert": top_k,
        "dry_run": dry_run,
        "samples": samples,
        "include_candidates": include_candidates,
        "candidate_limit": max_candidates,
        "candidates": candidate_rows if include_candidates else [],
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
def list_faults(page_size: int = Query(1000, ge=1, le=2000)) -> Dict[str, Any]:
    faults = _all_fault_names_ordered()
    # page_size 供前端自动补全限制返回量；默认全量
    limited = faults[:page_size]
    return {"faults": [{"name": n} for n in limited], "count": len(limited)}


@app.get("/graph/solutions")
def list_solutions(page_size: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    """轻量方案列表，供前端自动补全（仅返回 name）。"""
    script = """
g.V().hasLabel('Solution').order().by('name').limit(limit).values('name').fold()
"""
    rows = _extract_data(execute_gremlin(script, {"limit": page_size}))
    names: List[str] = rows[0] if rows and isinstance(rows[0], list) else []
    return {"solutions": [{"name": n} for n in names], "count": len(names)}


_FAULT_DETAIL_PROJ = """
.project('name','description','category','severity','domain','data_source','confidence','import_batch_id','created_at').
  by(values('name')).
  by(coalesce(values('description'), constant(''))).
  by(coalesce(values('category'), constant(''))).
  by(coalesce(values('severity'), constant(''))).
  by(coalesce(values('domain'), constant(''))).
  by(coalesce(values('data_source'), constant(''))).
  by(coalesce(values('confidence'), constant(1.0))).
  by(coalesce(values('import_batch_id'), constant(''))).
  by(coalesce(values('created_at'), constant(0)))
"""


def _normalize_fault_detail_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        conf = row.get("confidence", 1.0)
        try:
            conf_f = float(conf) if conf is not None else 1.0
        except (TypeError, ValueError):
            conf_f = 1.0
        try:
            ts = int(row.get("created_at") or 0)
        except (TypeError, ValueError):
            ts = 0
        out.append(
            {
                "name":             str(row.get("name") or ""),
                "description":      str(row.get("description") or ""),
                "category":         str(row.get("category") or ""),
                "severity":         str(row.get("severity") or ""),
                "domain":           str(row.get("domain") or ""),
                "data_source":      str(row.get("data_source") or ""),
                "confidence":       conf_f,
                "import_batch_id":  str(row.get("import_batch_id") or ""),
                "created_at":     ts,
            }
        )
    return out


def _safe_vertex_edge_counts() -> Dict[str, int]:
    """辅助前端理解：Fault 按名称唯一，Solution 与 HAS_SOLUTION 可远多于 Fault 数。"""
    try:
        fr = execute_gremlin("g.V().hasLabel('Fault').count()")
        sr = execute_gremlin("g.V().hasLabel('Solution').count()")
        er = execute_gremlin("g.E().hasLabel('HAS_SOLUTION').count()")
        return {
            "fault_vertex_count":   int((_extract_data(fr) or [0])[0]),
            "solution_vertex_count": int((_extract_data(sr) or [0])[0]),
            "has_solution_edge_count": int((_extract_data(er) or [0])[0]),
        }
    except Exception:
        return {"fault_vertex_count": 0, "solution_vertex_count": 0, "has_solution_edge_count": 0}


@app.get("/graph/faults/detail")
def list_faults_detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query("", max_length=200),
) -> Dict[str, Any]:
    """
    分页返回 Fault 顶点属性（供图谱管理页表格）。
    total 通过 _all_fault_names_ordered() 的列表长度计算，
    避免 HugeGraph .count() 偶发 refCnt 错误导致 total=0、翻页失效。
    """
    page_size = min(page_size, 200)
    counts = _safe_vertex_edge_counts()
    solution_total = counts["solution_vertex_count"]
    has_solution_edges = counts["has_solution_edge_count"]

    # 全量名单（分页 range 查询，不依赖 .count()）
    all_names = _all_fault_names_ordered()
    needle = (q or "").strip().lower()
    filtered = [n for n in all_names if needle in n.lower()] if needle else all_names

    total = len(filtered)
    graph_total = len(all_names)     # 无筛选时等于 total；筛选时保留原始总数
    offset = (page - 1) * page_size
    slice_names = filtered[offset : offset + page_size]

    base_resp: Dict[str, Any] = {
        "total":             total,
        "graph_total":       graph_total,
        "solution_total":    solution_total,
        "has_solution_edges": has_solution_edges,
        "page":              page,
        "page_size":         page_size,
        "q":                 q.strip(),
    }

    if not slice_names:
        return {"items": [], **base_resp}

    script = (
        "g.V().hasLabel('Fault').has('name', within(names))"
        + _FAULT_DETAIL_PROJ
    )
    rows = _extract_data(execute_gremlin(script, {"names": slice_names}))
    # within 结果顺序不定，按 slice_names 排序
    by_name = {str(r.get("name")): r for r in _normalize_fault_detail_rows(rows)}
    items = [by_name[n] for n in slice_names if n in by_name]
    return {"items": items, **base_resp}


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
def visualize_graph(
    fault_name: str,
    max_alerts: int = Query(8, ge=0, le=30),
    max_neighbors: int = Query(5, ge=0, le=20),
) -> Dict[str, Any]:
    """
    返回以某故障为中心的子图，包含：
    - Fault 本身
    - 关联 Solution（HAS_SOLUTION）
    - 触发该 Fault 的 Alert（TRIGGERS，最多 max_alerts 条）
    - 同 Category 的邻近 Fault（最多 max_neighbors 条，排除自身）
    """
    if not fault_name.strip():
        raise HTTPException(status_code=400, detail="fault_name cannot be empty")

    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen_node_ids: set = set()
    seen_edge_ids: set = set()

    def add_node(n: Dict) -> None:
        nid = str(n.get("id", ""))
        if nid and nid not in seen_node_ids:
            seen_node_ids.add(nid)
            nodes.append(n)

    def add_edge(e: Dict) -> None:
        eid = str(e.get("id", ""))
        if eid and eid not in seen_edge_ids:
            seen_edge_ids.add(eid)
            edges.append(e)

    # ── 1. Fault + Solutions ──────────────────────────────────────────────────
    ns = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).as('f').
  union(
    select('f').project('id','label','type').by(id()).by(values('name')).by(constant('Fault')),
    out('HAS_SOLUTION').project('id','label','type').by(id()).by(values('name')).by(constant('Solution'))
  )
""", {"fault_name": fault_name}))
    for n in ns:
        add_node(n)

    es = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  outE('HAS_SOLUTION').
  project('id','source','target','label').
    by(id()).by(outV().id()).by(inV().id()).by(label())
""", {"fault_name": fault_name}))
    for e in es:
        add_edge(e)

    # ── 2. Alert → TRIGGERS → Fault ──────────────────────────────────────────
    if max_alerts > 0:
        try:
            alert_nodes = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  in('TRIGGERS').hasLabel('Alert').
  limit(limit_n).
  project('id','label','type').by(id()).by(coalesce(values('alert_id'), values('name'), constant('Alert'))).by(constant('Alert'))
""", {"fault_name": fault_name, "limit_n": max_alerts}))
            for n in alert_nodes:
                add_node(n)

            alert_edges = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  inE('TRIGGERS').where(outV().hasLabel('Alert')).
  limit(limit_n).
  project('id','source','target','label').
    by(id()).by(outV().id()).by(inV().id()).by(label())
""", {"fault_name": fault_name, "limit_n": max_alerts}))
            for e in alert_edges:
                add_edge(e)
        except Exception:
            pass  # Alert 数据可选，查询失败不影响主图

    # ── 3. 同 Category 邻近 Fault ────────────────────────────────────────────
    if max_neighbors > 0:
        try:
            nbr_nodes = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  out('CLASSIFIED_AS').hasLabel('Category').
  in('CLASSIFIED_AS').hasLabel('Fault').
  where(values('name').is(neq(fault_name))).
  limit(limit_n).
  project('id','label','type').by(id()).by(values('name')).by(constant('Fault'))
""", {"fault_name": fault_name, "limit_n": max_neighbors}))
            for n in nbr_nodes:
                add_node(n)

            # Category 节点本身
            cat_nodes = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  out('CLASSIFIED_AS').hasLabel('Category').
  project('id','label','type').by(id()).by(values('name')).by(constant('Category'))
""", {"fault_name": fault_name}))
            for n in cat_nodes:
                add_node(n)

            # 主 Fault → Category 边
            cat_edges = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  outE('CLASSIFIED_AS').where(inV().hasLabel('Category')).
  project('id','source','target','label').
    by(id()).by(outV().id()).by(inV().id()).by(label())
""", {"fault_name": fault_name}))
            for e in cat_edges:
                add_edge(e)

            # 邻近 Fault → Category 边
            nbr_cat_edges = _extract_data(execute_gremlin("""
g.V().hasLabel('Fault').has('name', fault_name).
  out('CLASSIFIED_AS').hasLabel('Category').as('cat').
  in('CLASSIFIED_AS').hasLabel('Fault').
  where(values('name').is(neq(fault_name))).
  limit(limit_n).
  outE('CLASSIFIED_AS').where(inV().as('cat')).
  project('id','source','target','label').
    by(id()).by(outV().id()).by(inV().id()).by(label())
""", {"fault_name": fault_name, "limit_n": max_neighbors}))
            for e in nbr_cat_edges:
                add_edge(e)
        except Exception:
            pass

    return {
        "fault_name": fault_name,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@app.get("/graph/document-trace")
def graph_document_trace(document_id: str) -> Dict[str, Any]:
    """
    按 Dify document_id 反查图谱映射（Solution -> DOCUMENTED_IN -> SOP）。
    返回关联的 solution/fault，便于前端做双向追溯。
    """
    doc = str(document_id or "").strip()
    if not doc:
        raise HTTPException(status_code=400, detail="document_id cannot be empty")

    doc_vertex_name = f"dify-doc:{doc}"
    script = """
g.V().hasLabel('SOP').has('name', doc_name).as('d').
  inE('DOCUMENTED_IN').as('de').outV().hasLabel('Solution').as('s').
  project('document_id','document_vertex','solution_name','fault_names','chunk_ref').
    by(constant(doc_id)).
    by(select('d').values('name')).
    by(select('s').values('name')).
    by(select('s').in('HAS_SOLUTION').hasLabel('Fault').values('name').dedup().fold()).
    by(select('de').coalesce(values('chunk_ref'), constant('')))
"""
    rows = _extract_data(execute_gremlin(script, {"doc_name": doc_vertex_name, "doc_id": doc}))
    return {"document_id": doc, "items": rows, "count": len(rows)}


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
    all_faults: List[str] = _all_fault_names_ordered()

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
# Graph-RAG 上下文接口
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/chat/context")
def chat_context(q: str, top_k: int = 3) -> Dict[str, Any]:
    """
    为 AI 问答注入图谱上下文（Graph-RAG）。

    前端直接将返回值中的 `inputs` 字段传入 Dify chat-messages 的 `inputs` 参数，
    无需自行拼接 Prompt；Dify 工作流从 {{graph_context}} 变量中读取结构化知识。

    返回字段：
    - method       : 检索方式（vector / keyword / none）
    - inputs       : 可直接注入 Dify inputs 的 dict，包含 graph_context 和 query
    - summary_text : 纯文本摘要（备用，兼容旧版前端拼接模式）
    - recommendations : 原始推荐列表（供前端渲染参考面板）
    """
    if not q.strip():
        return {
            "method": "none",
            "inputs": {"graph_context": "", "query": q},
            "summary_text": "",
            "recommendations": [],
        }

    query_lower = q.lower()
    all_faults: List[str] = _all_fault_names_ordered()

    method = "keyword"
    top: List[Dict[str, Any]] = []

    if _vec.embedding_configured() and _vec.qdrant_collection_point_count() > 0:
        vec_hits = _vec.search_similar_faults(q, top_k)
        if vec_hits:
            method = "vector"
            top = [{"fault_name": fn, "similarity": round(sc, 4)} for fn, sc in vec_hits]

    if not top:
        method = "keyword" if method == "keyword" else "keyword_fallback"
        kw = _keyword_fault_scores(query_lower, all_faults)
        top = kw[:top_k]

    recommendations = _recommendations_payload(top)

    # 生成 Dify inputs.graph_context 字符串（结构化摘要，Jinja 友好）
    lines: List[str] = []
    for i, rec in enumerate(recommendations, 1):
        sols = "; ".join(
            f"{s.get('name','?')}（{s.get('description','')[:60]}）"
            for s in rec.get("solutions", [])
        ) or "暂无方案"
        sops = "、".join(rec.get("sop_titles", [])) or "暂无 SOP"
        lines.append(
            f"{i}. 故障：{rec['fault_name']}（相似度 {rec['similarity']}）\n"
            f"   方案：{sols}\n"
            f"   SOP：{sops}"
        )

    graph_context = (
        f"【图谱知识（Top-{len(recommendations)}，{method} 检索）】\n" + "\n".join(lines)
        if lines else ""
    )

    return {
        "method": method,
        "inputs": {"graph_context": graph_context, "query": q},
        "summary_text": graph_context,
        "recommendations": recommendations,
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
def list_assets(
    page: int = 1,
    page_size: int = 20,
    q: str = Query("", max_length=200),
) -> Dict[str, Any]:
    """
    资产分页列表。若传入 q（子串，忽略大小写），在 asset_id / name / ip 上过滤；
    此时先拉全量 Asset 再内存分页（资产规模通常远小于 Fault，可接受）。
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    needle = (q or "").strip().lower()

    proj = (
        "project('asset_id','name','asset_type','ip','env','data_source')."
        "by(values('asset_id')).by(coalesce(values('name'), constant('')))."
        "by(coalesce(values('asset_type'), constant('server')))."
        "by(coalesce(values('ip'), constant('')))."
        "by(coalesce(values('env'), constant('prod')))."
        "by(coalesce(values('data_source'), constant('manual')))"
    )

    if needle:
        rows = _gremlin_collect_paged(
            lambda lo, hi: (
                f"g.V().hasLabel('Asset').order().by('asset_id').range({lo}, {hi}).{proj.strip()}"
            ),
        )
        filtered: List[Dict[str, Any]] = []
        for a in rows or []:
            if not isinstance(a, dict):
                continue
            aid = str(a.get("asset_id", "") or "").lower()
            aname = str(a.get("name", "") or "").lower()
            aip = str(a.get("ip", "") or "").lower()
            if needle in aid or needle in aname or needle in aip:
                filtered.append(a)
        total = len(filtered)
        offset = (page - 1) * page_size
        slice_rows = filtered[offset : offset + page_size]
        return {"assets": slice_rows, "page": page, "page_size": page_size, "total": total, "q": q.strip()}

    offset = (page - 1) * page_size
    script = (
        "g.V().hasLabel('Asset').order().by('asset_id').range(offset, offset + limit)."
        + proj.strip()
    )
    result = execute_gremlin(script, {"offset": offset, "limit": page_size})
    assets = _extract_data(result)
    total_result = execute_gremlin("g.V().hasLabel('Asset').count()")
    total = int((_extract_data(total_result) or [0])[0])
    return {"assets": assets, "page": page, "page_size": page_size, "total": total, "q": ""}


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
g.V().hasLabel('Alert').order().by('occurred_at', Order.desc).range(offset, offset + limit).
  project('alert_id','content','level','source','occurred_at').
    by(values('alert_id')).by(values('content')).
    by(values('level')).by(values('source')).
    by(coalesce(values('occurred_at'), constant(0)))
"""
        result = execute_gremlin(script, {"offset": offset, "limit": page_size})
    alerts = _extract_data(result)
    return {"alerts": alerts, "page": page, "page_size": page_size}


@app.get("/admin/triggers/audit")
def admin_triggers_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    method: str = Query("", max_length=20),
    rule_name: str = Query("", max_length=200),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    """
    分页返回 TRIGGERS 审计明细（Alert -> Fault）。
    支持 method/rule_name/min_confidence 过滤，供前端审计页展示。
    """
    rows = _gremlin_collect_paged(
        lambda lo, hi: (
            "g.E().hasLabel('TRIGGERS').order().by('created_at')"
            f".range({lo}, {hi})"
            ".project('edge_id','alert_id','fault_name','confidence','method','rule_name','created_at')"
            ".by(id())"
            ".by(outV().values('alert_id'))"
            ".by(inV().values('name'))"
            ".by(coalesce(values('confidence'), constant(0.0)))"
            ".by(coalesce(values('method'), constant('')))"
            ".by(coalesce(values('rule_name'), constant('')))"
            ".by(coalesce(values('created_at'), constant(0)))"
        )
    )

    method_filter = (method or "").strip().lower()
    rule_filter = (rule_name or "").strip().lower()
    min_conf = float(min_confidence)

    normalized: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {
            "edge_id": str(row.get("edge_id", "")),
            "alert_id": str(row.get("alert_id", "")),
            "fault_name": str(row.get("fault_name", "")),
            "confidence": float(row.get("confidence", 0.0) or 0.0),
            "method": str(row.get("method", "") or ""),
            "rule_name": str(row.get("rule_name", "") or ""),
            "created_at": int(row.get("created_at", 0) or 0),
        }
        if method_filter and item["method"].lower() != method_filter:
            continue
        if rule_filter and rule_filter not in item["rule_name"].lower():
            continue
        if item["confidence"] < min_conf:
            continue
        normalized.append(item)

    total = len(normalized)
    offset = (page - 1) * page_size
    items = normalized[offset : offset + page_size]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "method": method_filter,
        "rule_name": rule_name.strip(),
        "min_confidence": min_conf,
    }


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


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> Dict[str, Any]:
    """工单详情（含关联 Fault / Solution / Asset 边）。"""
    base_script = """
g.V().hasLabel('Incident').has('incident_id', incident_id).
  project('incident_id','title','status','mttr_minutes','created_at','data_source').
    by(values('incident_id')).by(values('title')).
    by(coalesce(values('status'), constant('closed'))).
    by(coalesce(values('mttr_minutes'), constant(0))).
    by(coalesce(values('created_at'), constant(0))).
    by(coalesce(values('data_source'), constant('manual')))
"""
    rows = _extract_data(execute_gremlin(base_script, {"incident_id": incident_id}))
    if not rows:
        raise HTTPException(status_code=404, detail="incident not found")
    detail = rows[0]

    # 关联 Fault（CAUSED_BY）
    fault_script = """
g.V().hasLabel('Incident').has('incident_id', incident_id).
  out('CAUSED_BY').hasLabel('Fault').values('name').fold()
"""
    faults = _extract_data(execute_gremlin(fault_script, {"incident_id": incident_id}))
    detail["faults"] = faults[0] if faults else []

    # 关联 Solution（RESOLVED_BY）
    sol_script = """
g.V().hasLabel('Incident').has('incident_id', incident_id).
  out('RESOLVED_BY').hasLabel('Solution').
  project('name','description').
    by(values('name')).
    by(coalesce(values('description'), constant(''))).fold()
"""
    sols = _extract_data(execute_gremlin(sol_script, {"incident_id": incident_id}))
    detail["solutions"] = sols[0] if sols else []

    # 关联 Asset（INVOLVES）
    asset_script = """
g.V().hasLabel('Incident').has('incident_id', incident_id).
  out('INVOLVES').hasLabel('Asset').
  project('asset_id','name','asset_type','ip').
    by(values('asset_id')).
    by(coalesce(values('name'), constant(''))).
    by(coalesce(values('asset_type'), constant(''))).
    by(coalesce(values('ip'), constant(''))).fold()
"""
    assets = _extract_data(execute_gremlin(asset_script, {"incident_id": incident_id}))
    detail["assets"] = assets[0] if assets else []

    return detail


@app.get("/incidents")
def list_incidents(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    script = """
g.V().hasLabel('Incident').order().by('created_at', Order.desc).range(offset, offset + limit).
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

def _extract_json_array_from_llm(content: str) -> List[Dict[str, Any]]:
    content = (content or "").strip()
    if not content:
        return []
    start = content.find("[")
    end = content.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    raw = content[start:end]
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        fault_name = str(row.get("fault_name", "")).strip()
        solution_name = str(row.get("solution_name", "")).strip()
        solution_desc = str(row.get("solution_description", "")).strip()
        if not fault_name or not solution_name:
            continue
        try:
            conf = float(row.get("confidence", 0.7))
        except Exception:
            conf = 0.7
        conf = max(0.0, min(conf, 1.0))
        out.append(
            {
                "fault_name": fault_name[:200],
                "solution_name": solution_name[:200],
                "solution_description": solution_desc[:2000],
                "confidence": conf,
            }
        )
    return out


def _sync_approved_to_dify(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    同步已审核知识到 Dify 数据集（可选配置）。
    成功返回 {"ok": True, "message": "..."}，失败返回 {"ok": False, "message": "..."}。
    """
    if not (DIFY_DATASET_API_URL and DIFY_DATASET_ID and DIFY_DATASET_API_KEY):
        return {"ok": False, "message": "dify_dataset_not_configured"}

    headers = {
        "Authorization": f"Bearer {DIFY_DATASET_API_KEY}",
        "Content-Type": "application/json",
    }

    doc_name = f"{item.get('fault_name', 'fault')[:80]}-{item.get('id', '')}"
    doc_text = (
        f"故障: {item.get('fault_name', '')}\n"
        f"方案: {item.get('solution_name', '')}\n"
        f"描述: {item.get('solution_description', '')}\n"
        f"来源: {item.get('source_hint', '')}\n"
        f"置信度: {item.get('confidence', 0.7)}"
    )

    payload = {
        "name": doc_name,
        "text": doc_text,
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
    }

    candidates = [
        f"{DIFY_DATASET_API_URL}/datasets/{DIFY_DATASET_ID}/document/create-by-text",
        f"{DIFY_DATASET_API_URL}/datasets/{DIFY_DATASET_ID}/documents/create-by-text",
    ]
    last_err = ""
    for url in candidates:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.ok:
                body = {}
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                return {
                    "ok": True,
                    "message": "synced",
                    "document_id": str(body.get("document", {}).get("id", "") or body.get("id", "")),
                    "endpoint": url,
                }
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as e:
            last_err = str(e)
    return {"ok": False, "message": last_err or "dify_sync_failed"}


def _link_solution_to_dify_document(item: Dict[str, Any], document_id: str) -> Dict[str, Any]:
    """
    将已审核 Solution 与 Dify 文档建立 DOCUMENTED_IN 映射。
    采用“Solution -> SOP(虚拟文档节点)”边，并将 document_id 写入 chunk_ref。
    """
    if not document_id:
        return {"ok": False, "message": "empty_document_id"}
    try:
        solution_name = str(item.get("solution_name", "") or "").strip()
        if not solution_name:
            return {"ok": False, "message": "empty_solution_name"}

        # 1) 确保 Solution 顶点存在
        s_rows = _extract_data(
            execute_gremlin(
                "g.V().hasLabel('Solution').has('name', sname).id()",
                {"sname": solution_name},
            )
        )
        if not s_rows:
            return {"ok": False, "message": "solution_not_found"}
        sid = str(s_rows[0])

        # 2) 创建/复用 SOP 虚拟文档顶点（name 是主键）
        doc_vertex_name = f"dify-doc:{document_id}"
        doc_vertex_id = _upsert_vertex(
            "SOP",
            doc_vertex_name,
            {
                "title": f"Dify Document {document_id}",
                "steps": "",
                "version": "1.0",
                "author": "dify-sync",
                "data_source": "dify_dataset",
                "confidence": 1.0,
            },
        )
        if not doc_vertex_id:
            return {"ok": False, "message": "document_vertex_upsert_failed"}

        # 3) 幂等创建 DOCUMENTED_IN 边，并写 chunk_ref=document_id
        exists = _extract_data(
            execute_gremlin(
                "g.V(sid).outE('DOCUMENTED_IN').where(__.inV().hasId(did)).count()",
                {"sid": sid, "did": doc_vertex_id},
            )
        )
        if int((exists or [0])[0]) == 0:
            execute_gremlin(
                "def sv = g.V(sid).next(); def dv = g.V(did).next(); "
                "g.addE('DOCUMENTED_IN').from(sv).to(dv).property('chunk_ref', docid).iterate()",
                {"sid": sid, "did": doc_vertex_id, "docid": document_id},
            )
            edge_status = "created"
        else:
            execute_gremlin(
                "g.V(sid).outE('DOCUMENTED_IN').where(__.inV().hasId(did)).property('chunk_ref', docid).iterate()",
                {"sid": sid, "did": doc_vertex_id, "docid": document_id},
            )
            edge_status = "updated"

        return {
            "ok": True,
            "message": edge_status,
            "solution_id": sid,
            "document_vertex_id": doc_vertex_id,
            "document_vertex_name": doc_vertex_name,
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _llm_extract(text: str, job_id: str, source_hint: str) -> None:
    """后台异步抽取任务（调用真实 LLM，失败时规则降级）"""
    _extract_jobs[job_id]["status"] = "running"
    _extract_jobs[job_id]["started_at"] = int(time.time() * 1000)
    candidates: List[Dict[str, Any]] = []
    used_mode = "fallback_rule"

    if LLM_API_URL and LLM_API_KEY:
        try:
            prompt = f"""你是一名 IT 运维知识工程师。请从以下文本中提取故障–解决方案关系，
以 JSON 数组输出，每项包含：
  fault_name（字符串）
  solution_name（字符串）
  solution_description（字符串，不超过500字）
  confidence（0.0~1.0）

文本：
{text[:12000]}

仅输出 JSON 数组，不要其他内容。"""

            resp = requests.post(
                LLM_API_URL,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_CHAT_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                timeout=90,
            )
            if resp.ok:
                content = resp.json()["choices"][0]["message"]["content"]
                candidates = _extract_json_array_from_llm(content)
                if candidates:
                    used_mode = "llm"
            else:
                _extract_jobs[job_id]["error"] = f"llm_http_{resp.status_code}"
        except Exception as e:
            _extract_jobs[job_id]["error"] = str(e)

    # 降级：逐行规则抽取
    if not candidates:
        for line in text.split("\n"):
            line = line.strip()
            if "故障" in line and ("解决" in line or "方案" in line or "处理" in line):
                candidates.append(
                    {
                        "fault_name": line[:80],
                        "solution_name": "待补充",
                        "solution_description": line[:500],
                        "confidence": 0.5,
                    }
                )

    # 写入审核队列
    now = int(time.time() * 1000)
    for c in candidates:
        qid = str(uuid.uuid4())[:8]
        _extract_queue[qid] = {
            "id": qid,
            "job_id": job_id,
            "source_hint": source_hint,
            "fault_name": c.get("fault_name", ""),
            "solution_name": c.get("solution_name", ""),
            "solution_description": c.get("solution_description", ""),
            "confidence": c.get("confidence", 0.7),
            "extract_mode": used_mode,
            "status": "pending",
            "created_at": now,
        }

    _extract_jobs[job_id]["status"] = "done"
    _extract_jobs[job_id]["extract_mode"] = used_mode
    _extract_jobs[job_id]["candidate_count"] = len(candidates)
    _extract_jobs[job_id]["finished_at"] = int(time.time() * 1000)


@app.post("/extract/submit")
def extract_submit(payload: ExtractSubmitRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())[:12]
    _extract_jobs[job_id] = {
        "job_id":      job_id,
        "source_hint": payload.source_hint,
        "status":      "pending",
        "created_at":  int(time.time() * 1000),
        "started_at":  0,
        "finished_at": 0,
        "candidate_count": 0,
        "extract_mode": "",
        "error": "",
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


def _approve_extract_item(item_id: str) -> Dict[str, Any]:
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
    add_relation(req, BackgroundTasks())
    item["status"] = "approved"
    item["approved_at"] = int(time.time() * 1000)

    dify_result = _sync_approved_to_dify(item)
    item["dify_sync"] = dify_result
    if dify_result.get("ok"):
        item["dify_status"] = "synced"
        item["document_id"] = str(dify_result.get("document_id", "") or "")
        graph_link = _link_solution_to_dify_document(item, item["document_id"])
        item["graph_document_link"] = graph_link
        _extract_doc_links.append(
            {
                "item_id": item_id,
                "job_id": item.get("job_id", ""),
                "fault_name": item.get("fault_name", ""),
                "solution_name": item.get("solution_name", ""),
                "document_id": item.get("document_id", ""),
                "created_at": int(time.time() * 1000),
                "graph_document_link": graph_link,
            }
        )
    else:
        item["dify_status"] = "skipped_or_failed"

    return {
        "status": "ok",
        "item_id": item_id,
        "message": "已写入图谱",
        "dify_sync": dify_result,
        "graph_document_link": item.get("graph_document_link", {}),
    }


@app.post("/extract/queue/{item_id}/approve")
def approve_extract(item_id: str) -> Dict[str, Any]:
    return _approve_extract_item(item_id)


@app.post("/extract/queue/batch-approve")
def batch_approve_extract(payload: ExtractBatchIdsRequest) -> Dict[str, Any]:
    seen: set = set()
    ordered: List[str] = []
    for raw in payload.item_ids:
        tid = (raw or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        ordered.append(tid)
    if len(ordered) > 50:
        raise HTTPException(status_code=400, detail="batch size exceeds 50")

    results: List[Dict[str, Any]] = []
    for tid in ordered:
        try:
            data = _approve_extract_item(tid)
            results.append({"item_id": tid, "ok": True, "data": data})
        except HTTPException as he:
            results.append({"item_id": tid, "ok": False, "error": he.detail})

    ok_n = sum(1 for r in results if r.get("ok"))
    return {"results": results, "succeeded": ok_n, "failed": len(results) - ok_n}


@app.get("/extract/doc-links")
def list_extract_doc_links(job_id: str = "", limit: int = 100) -> Dict[str, Any]:
    rows = list(_extract_doc_links)
    if job_id.strip():
        rows = [r for r in rows if str(r.get("job_id", "")) == job_id.strip()]
    rows.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
    lim = max(1, min(int(limit), 500))
    return {"items": rows[:lim], "total": len(rows)}


@app.post("/extract/queue/{item_id}/reject")
def reject_extract(item_id: str) -> Dict[str, Any]:
    if item_id not in _extract_queue:
        raise HTTPException(status_code=404, detail="item not found")
    _extract_queue[item_id]["status"] = "rejected"
    return {"status": "ok", "item_id": item_id}


@app.post("/extract/queue/batch-reject")
def batch_reject_extract(payload: ExtractBatchIdsRequest) -> Dict[str, Any]:
    seen: set = set()
    ordered: List[str] = []
    for raw in payload.item_ids:
        tid = (raw or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        ordered.append(tid)
    if len(ordered) > 50:
        raise HTTPException(status_code=400, detail="batch size exceeds 50")

    results: List[Dict[str, Any]] = []
    for tid in ordered:
        if tid not in _extract_queue:
            results.append({"item_id": tid, "ok": False, "error": "item not found"})
            continue
        _extract_queue[tid]["status"] = "rejected"
        results.append({"item_id": tid, "ok": True})

    ok_n = sum(1 for r in results if r.get("ok"))
    return {"results": results, "succeeded": ok_n, "failed": len(results) - ok_n}


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

    # Fault 按 data_source 分布：
    # 改为分页拉取 Fault 顶点属性后在内存聚合，避免 Gremlin count/not(__.has()) 在部分环境报错
    source_dist: Dict[str, int] = {}
    try:
        rows = _gremlin_collect_paged(
            lambda lo, hi: (
                "g.V().hasLabel('Fault').order().by('name')"
                f".range({lo}, {hi})"
                ".project('name','data_source')"
                ".by(values('name'))"
                ".by(coalesce(values('data_source'), constant('unset')))"
            )
        )
        for row in rows:
            if not isinstance(row, dict):
                continue
            src = row.get("data_source", "unset")
            key = str(src).strip() if src is not None else "unset"
            if not key:
                key = "unset"
            source_dist[key] = source_dist.get(key, 0) + 1
    except Exception:
        source_dist = {}

    def _edge_cnt(lbl: str) -> int:
        try:
            r = execute_gremlin(f"g.E().hasLabel('{lbl}').count()")
            return int((_extract_data(r) or [0])[0])
        except Exception:
            # 某些 HugeGraph 版本在 edge count() 上会触发异常，降级为分页取 id 后计数
            try:
                rows = _gremlin_collect_paged(
                    lambda lo, hi: f"g.E().hasLabel('{lbl}').range({lo}, {hi}).id()"
                )
                return len(rows or [])
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
