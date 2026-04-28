import os
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="WisOps Graph API",
    root_path="/graph-api",          # 告知 Swagger UI 通过网关的子路径访问
    root_path_in_servers=False,
)

HUGEGRAPH_URL = os.getenv("HUGEGRAPH_URL", "http://localhost:8081").rstrip("/")
HUGEGRAPH_GRAPH = os.getenv("HUGEGRAPH_GRAPH", "hugegraph")
REQUEST_TIMEOUT = 10
_ACTIVE_GREMLIN_ENDPOINT: Optional[str] = None


class AddRelationRequest(BaseModel):
    fault_name: str = Field(..., min_length=1, max_length=200)
    solution_name: str = Field(..., min_length=1, max_length=200)
    solution_description: str = Field(default="", max_length=2000)


def _extract_data(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result", {})
    data = result.get("data", [])
    if not isinstance(data, list):
        return []
    return data


def _candidate_gremlin_endpoints() -> List[str]:
    return [
        f"{HUGEGRAPH_URL}/graphs/{HUGEGRAPH_GRAPH}/gremlin",
        f"{HUGEGRAPH_URL}/gremlin",
        f"{HUGEGRAPH_URL}/graphs/hugegraph/gremlin",
        f"{HUGEGRAPH_URL}/graphs/wisops/gremlin",
    ]


def execute_gremlin(gremlin: str, bindings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    global _ACTIVE_GREMLIN_ENDPOINT

    # HugeGraph 全局 Gremlin context 中没有 graph/g，需要用具体图名
    # 例如默认图名是 "hugegraph"，则 hugegraph.traversal()
    gremlin = gremlin.replace("graph.traversal()", f"{HUGEGRAPH_GRAPH}.traversal()")
    gremlin = gremlin.replace("graph.schema()", f"{HUGEGRAPH_GRAPH}.schema()")

    # 在普通查询脚本前自动注入 g
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
            raise HTTPException(
                status_code=502,
                detail=f"HugeGraph error {resp.status_code} ({endpoint}): {resp.text}",
            )

        _ACTIVE_GREMLIN_ENDPOINT = endpoint
        return resp.json()

    raise HTTPException(
        status_code=503,
        detail=f"HugeGraph unavailable or Gremlin endpoint not found: {last_error}",
    )


def ensure_schema() -> None:
    schema_script = """
schema = graph.schema()
schema.propertyKey('name').asText().ifNotExist().create()
schema.propertyKey('description').asText().ifNotExist().create()
schema.vertexLabel('Fault').properties('name').primaryKeys('name').ifNotExist().create()
schema.vertexLabel('Solution').properties('name', 'description').primaryKeys('name').ifNotExist().create()
schema.edgeLabel('HAS_SOLUTION').sourceLabel('Fault').targetLabel('Solution').ifNotExist().create()
"""
    execute_gremlin(schema_script)


@app.on_event("startup")
def startup() -> None:
    # Keep startup non-fatal to avoid crash loops when HugeGraph boots slowly.
    try:
        ensure_schema()
    except HTTPException:
        pass


@app.get("/health")
def health() -> Dict[str, str]:
    try:
        execute_gremlin("g.V().limit(1)")
        return {"status": "ok", "hugegraph": "connected"}
    except HTTPException:
        return {"status": "degraded", "hugegraph": "disconnected"}


@app.post("/graph/add")
def add_relation(payload: AddRelationRequest) -> Dict[str, Any]:
    ensure_schema()
    add_script = """
def f = g.V().hasLabel('Fault').has('name', fault_name).fold().
      coalesce(__.unfold(), __.addV('Fault').property('name', fault_name)).next()
def s = g.V().hasLabel('Solution').has('name', solution_name).fold().
      coalesce(__.unfold(),
               __.addV('Solution').property('name', solution_name).property('description', solution_description)).next()
def sid = s.id()
if (g.V(f).outE('HAS_SOLUTION').where(__.inV().hasId(sid)).hasNext()) {
  'exists'
} else {
  g.V(f).as('a').V(sid).addE('HAS_SOLUTION').from('a').next()
  'created'
}
"""
    result = execute_gremlin(
        add_script,
        {
            "fault_name": payload.fault_name,
            "solution_name": payload.solution_name,
            "solution_description": payload.solution_description,
        },
    )
    data = _extract_data(result)
    state = data[0] if data else "unknown"
    return {"status": "ok", "edge_status": state}


@app.get("/graph/faults")
def list_faults() -> Dict[str, Any]:
    script = "g.V().hasLabel('Fault').values('name').order()"
    result = execute_gremlin(script)
    faults = _extract_data(result)
    return {"faults": faults, "count": len(faults)}


@app.get("/graph/query")
def query_solutions(fault_name: str) -> Dict[str, Any]:
    if not fault_name.strip():
        raise HTTPException(status_code=400, detail="fault_name cannot be empty")

    query_script = """
g.V().hasLabel('Fault').has('name', fault_name).
  out('HAS_SOLUTION').
  project('id', 'name', 'description').
    by(id()).
    by(values('name')).
    by(coalesce(values('description'), constant('')))
"""
    result = execute_gremlin(query_script, {"fault_name": fault_name})
    rows = _extract_data(result)
    return {"fault_name": fault_name, "solutions": rows, "count": len(rows)}