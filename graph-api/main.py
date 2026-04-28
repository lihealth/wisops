"""WisOps Graph API — V2.0"""
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
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
    fault_name:           str = Field(..., min_length=1, max_length=200)
    solution_name:        str = Field(..., min_length=1, max_length=200)
    solution_description: str = Field(default="", max_length=2000)
    data_source:          str = Field(default="manual")
    confidence:           float = Field(default=1.0, ge=0.0, le=1.0)
    import_batch_id:      str = Field(default="")

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
    gremlin = gremlin.replace("graph.traversal()", f"{HUGEGRAPH_GRAPH}.traversal()")
    gremlin = gremlin.replace("graph.schema()",    f"{HUGEGRAPH_GRAPH}.schema()")
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
    """幂等执行 V2.0 Schema 初始化"""
    schema_dir = os.path.dirname(__file__)
    schema_file = os.path.join(schema_dir, "schema_v2.groovy")
    if not os.path.exists(schema_file):
        _ensure_schema_v1()
        return
    with open(schema_file, "r", encoding="utf-8") as f:
        script = f.read()
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


@app.post("/graph/add")
def add_relation(payload: AddRelationRequest) -> Dict[str, Any]:
    now = int(time.time() * 1000)
    script = """
def f = g.V().hasLabel('Fault').has('name', fault_name).fold().
      coalesce(__.unfold(),
               __.addV('Fault').property('name', fault_name)
                               .property('data_source', data_source)
                               .property('confidence', confidence)
                               .property('created_at', ts)).next()
def s = g.V().hasLabel('Solution').has('name', solution_name).fold().
      coalesce(__.unfold(),
               __.addV('Solution').property('name', solution_name)
                                  .property('description', solution_description)
                                  .property('data_source', data_source)
                                  .property('confidence', confidence)
                                  .property('created_at', ts)).next()
def sid = s.id()
if (g.V(f).outE('HAS_SOLUTION').where(__.inV().hasId(sid)).hasNext()) {
  'exists'
} else {
  g.V(f).as('a').V(sid).addE('HAS_SOLUTION').from('a').next()
  'created'
}
"""
    result = execute_gremlin(script, {
        "fault_name":           payload.fault_name,
        "solution_name":        payload.solution_name,
        "solution_description": payload.solution_description,
        "data_source":          payload.data_source,
        "confidence":           payload.confidence,
        "ts":                   now,
    })
    data = _extract_data(result)
    state = data[0] if data else "unknown"
    return {"status": "ok", "edge_status": state}


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


@app.post("/graph/recommend")
def recommend_faults(payload: RecommendRequest) -> Dict[str, Any]:
    """
    相似故障推荐：基于关键词模糊匹配（V2.0 基础版）。
    V2.1 升级：接入 Qdrant fault_vectors embedding 检索。
    """
    query = payload.query.lower()

    # 获取所有故障名
    all_faults_result = execute_gremlin("g.V().hasLabel('Fault').values('name').order()")
    all_faults: List[str] = _extract_data(all_faults_result)

    # 简单关键词评分（待替换为 embedding 相似度）
    scored: List[Dict[str, Any]] = []
    for fname in all_faults:
        score = 0.0
        fname_lower = fname.lower()
        # 完整包含：高分
        if query in fname_lower or fname_lower in query:
            score = 0.9
        else:
            # 词粒度交集
            q_words = set(query.replace("，", " ").replace(",", " ").split())
            f_words = set(fname_lower.replace("，", " ").replace(",", " ").split())
            intersection = q_words & f_words
            if intersection:
                score = len(intersection) / max(len(q_words), len(f_words))
        if score > 0:
            scored.append({"fault_name": fname, "similarity": round(score, 3)})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    top = scored[: payload.top_k]

    # 为每个推荐结果查询方案
    recommendations = []
    for item in top:
        sol_result = execute_gremlin(
            "g.V().hasLabel('Fault').has('name', fault_name).out('HAS_SOLUTION')"
            ".project('name','description').by(values('name')).by(coalesce(values('description'), constant('')))",
            {"fault_name": item["fault_name"]}
        )
        solutions = _extract_data(sol_result)

        sop_result = execute_gremlin(
            "g.V().hasLabel('Fault').has('name', fault_name).out('HAS_SOP').values('title')",
            {"fault_name": item["fault_name"]}
        )
        sop_titles = _extract_data(sop_result)

        recommendations.append({
            "fault_name":  item["fault_name"],
            "similarity":  item["similarity"],
            "solutions":   solutions,
            "sop_titles":  sop_titles,
        })

    return {
        "query":           payload.query,
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
                json={"model": "gpt-4o-mini",
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
    def _count(label: str) -> int:
        r = execute_gremlin(f"g.V().hasLabel('{label}').count()")
        return (_extract_data(r) or [0])[0]

    fault_count    = _count("Fault")
    solution_count = _count("Solution")
    sop_count      = _count("SOP")
    asset_count    = _count("Asset")
    incident_count = _count("Incident")
    alert_count    = _count("Alert")

    # 知识覆盖率：有 Solution 的 Fault / 总 Fault
    covered_result = execute_gremlin(
        "g.V().hasLabel('Fault').where(out('HAS_SOLUTION')).count()"
    )
    covered = (_extract_data(covered_result) or [0])[0]
    coverage_rate = round(covered / fault_count * 100, 1) if fault_count > 0 else 0.0

    # 按 data_source 分布
    source_result = execute_gremlin(
        "g.V().hasLabel('Fault').groupCount().by(coalesce(values('data_source'), constant('unknown')))"
    )
    source_dist = (_extract_data(source_result) or [{}])[0]

    # 方案复用率
    resolved_result = execute_gremlin(
        "g.V().hasLabel('Incident').where(out('RESOLVED_BY')).count()"
    )
    resolved = (_extract_data(resolved_result) or [0])[0]
    reuse_rate = round(resolved / incident_count * 100, 1) if incident_count > 0 else 0.0

    # 抽取转化率
    approved = sum(1 for v in _extract_queue.values() if v["status"] == "approved")
    total_q  = len(_extract_queue)
    extract_rate = round(approved / total_q * 100, 1) if total_q > 0 else 0.0

    return {
        "node_counts": {
            "Fault":    fault_count,
            "Solution": solution_count,
            "SOP":      sop_count,
            "Asset":    asset_count,
            "Incident": incident_count,
            "Alert":    alert_count,
        },
        "coverage_rate":   coverage_rate,
        "reuse_rate":      reuse_rate,
        "extract_rate":    extract_rate,
        "source_distribution": source_dist,
        "extract_queue": {
            "total":    total_q,
            "pending":  sum(1 for v in _extract_queue.values() if v["status"] == "pending"),
            "approved": approved,
            "rejected": sum(1 for v in _extract_queue.values() if v["status"] == "rejected"),
        },
    }


@app.get("/ops/stats/growth")
def ops_growth(window: str = "week") -> Dict[str, Any]:
    """节点增长趋势（按时间窗口）- 基础版：返回当前快照"""
    now = int(time.time() * 1000)
    if window == "week":
        since = now - 7 * 24 * 3600 * 1000
    elif window == "month":
        since = now - 30 * 24 * 3600 * 1000
    else:
        since = 0

    for label in ["Fault", "Solution", "SOP"]:
        r = execute_gremlin(
            f"g.V().hasLabel('{label}').has('created_at', gte(ts)).count()",
            {"ts": since}
        )
        count = (_extract_data(r) or [0])[0]

    fault_r = execute_gremlin("g.V().hasLabel('Fault').has('created_at', gte(ts)).count()", {"ts": since})
    sol_r   = execute_gremlin("g.V().hasLabel('Solution').has('created_at', gte(ts)).count()", {"ts": since})
    sop_r   = execute_gremlin("g.V().hasLabel('SOP').has('created_at', gte(ts)).count()", {"ts": since})

    return {
        "window": window,
        "since_ms": since,
        "new_nodes": {
            "Fault":    (_extract_data(fault_r) or [0])[0],
            "Solution": (_extract_data(sol_r) or [0])[0],
            "SOP":      (_extract_data(sop_r) or [0])[0],
        }
    }
