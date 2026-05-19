import { useState, useEffect, useRef, useCallback } from 'react'
import { useRole } from '../RoleContext'
import './GraphPage.css'

const GRAPH_BASE = '/graph-api'

const FAULT_PAGE_SIZE_OPTIONS = [50, 100, 200] as const

interface FaultRow {
  name: string
  description: string
  category: string
  severity: string
  domain: string
  data_source: string
  confidence: number
  import_batch_id: string
  created_at: number
}

interface TriggerAuditRow {
  edge_id: string
  alert_id: string
  fault_name: string
  confidence: number
  method: string
  rule_name: string
  created_at: number
}

interface Solution { id: string; name: string; description: string }
interface GraphNode { id: string; label: string; type: 'Fault' | 'Solution' }
interface GraphEdge { id: string; source: string; target: string; label: string }

export default function GraphPage() {
  const { can } = useRole()
  const canWrite = can('write_graph')
  const [tab, setTab] = useState<'query' | 'add' | 'visual' | 'catalog' | 'triggers' | 'docTrace'>('query')

  return (
    <div className="graph-page">
      <div className="graph-header">
        <span className="graph-title">故障图谱管理</span>
        <div className="graph-tabs">
          <button className={tab === 'query' ? 'tab active' : 'tab'} onClick={() => setTab('query')}>查询方案</button>
          <button className={tab === 'visual' ? 'tab active' : 'tab'} onClick={() => setTab('visual')}>图谱可视化</button>
          <button className={tab === 'catalog' ? 'tab active' : 'tab'} onClick={() => setTab('catalog')}>故障列表</button>
          <button className={tab === 'triggers' ? 'tab active' : 'tab'} onClick={() => setTab('triggers')}>TRIGGERS 审计</button>
          <button className={tab === 'docTrace' ? 'tab active' : 'tab'} onClick={() => setTab('docTrace')}>文档追溯</button>
          {canWrite && (
            <button className={tab === 'add' ? 'tab active' : 'tab'} onClick={() => setTab('add')}>录入故障</button>
          )}
        </div>
      </div>
      <div className="graph-body">
        {tab === 'query' && <QueryPanel />}
        {tab === 'visual' && <VisualPanel />}
        {tab === 'catalog' && <FaultTablePanel />}
        {tab === 'triggers' && <TriggersAuditPanel />}
        {tab === 'docTrace' && <DocumentTracePanel />}
        {tab === 'add' && (canWrite ? <AddPanel /> : null)}
      </div>
    </div>
  )
}

function formatFaultTime(ms: number): string {
  if (!ms || ms <= 0) return '—'
  try {
    return new Date(ms).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return '—'
  }
}

function FaultTablePanel() {
  const [items, setItems] = useState<FaultRow[]>([])
  const [total, setTotal] = useState(0)
  const [graphTotal, setGraphTotal] = useState(0)
  const [solutionTotal, setSolutionTotal] = useState(0)
  const [hasSolutionEdges, setHasSolutionEdges] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setQ(qInput.trim()), 350)
    return () => window.clearTimeout(t)
  }, [qInput])

  useEffect(() => {
    setPage(1)
  }, [q])

  useEffect(() => {
    setPage(1)
  }, [pageSize])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (q) params.set('q', q)
    fetch(`${GRAPH_BASE}/graph/faults/detail?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (cancelled) return
        setItems(d.items ?? [])
        setTotal(typeof d.total === 'number' ? d.total : 0)
        setGraphTotal(typeof d.graph_total === 'number' ? d.graph_total : (d.total ?? 0))
        setSolutionTotal(typeof d.solution_total === 'number' ? d.solution_total : 0)
        setHasSolutionEdges(typeof d.has_solution_edges === 'number' ? d.has_solution_edges : 0)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : '加载失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, q, pageSize])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1
  const rangeEnd = total === 0 ? 0 : Math.min(page * pageSize, total)

  return (
    <div className="panel fault-table-panel">
      <p className="fault-table-hint">
        本表每一行是图谱里的一个 <strong>Fault</strong> 顶点（<strong>故障名称唯一</strong>，多行导入若归为同一类故障会合并为一行）。
        当前图中：<strong>{graphTotal}</strong> 个故障、<strong>{solutionTotal}</strong> 个解决方案、
        <strong>{hasSolutionEdges}</strong> 条「故障—方案」关联。
        {q ? ` 筛选后本表共 ${total} 行。` : ' '}
        行数多于每页条数时可用「上一页 / 下一页」；若总页数为 1，说明<strong>图中故障类型就只有这么多</strong>（例如 GAIA 导入脚本按有限类模板 + 故障名去重归类，不等于原始日志行数或千条 JSONL 行数）。
      </p>
      <div className="fault-table-toolbar">
        <input
          className="text-input fault-table-search"
          placeholder="按名称筛选（子串匹配）…"
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
        />
        <label className="fault-page-size-label">
          每页
          <select
            className="fault-page-size"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            aria-label="每页条数"
          >
            {FAULT_PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>{n} 条</option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="msg-error">{error}</div>}
      {loading && <div className="empty">加载中…</div>}

      {!loading && !error && total > 0 && (
        <div className="fault-table-range">
          显示第 {rangeStart}–{rangeEnd} 条，共 {total} 条（第 {page} / {totalPages} 页）
        </div>
      )}

      {!loading && total > 0 && (
        <div className="pagination pagination-top">
          <button
            type="button"
            className="btn-page"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span className="page-info">
            第 {page} / {totalPages} 页
          </span>
          <button
            type="button"
            className="btn-page"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            下一页
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="fault-table-wrap">
          <table className="fault-table">
            <thead>
              <tr>
                <th>故障名称</th>
                <th>描述</th>
                <th>领域</th>
                <th>来源</th>
                <th>严重级别</th>
                <th>分类</th>
                <th>置信度</th>
                <th>录入时间</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="fault-table-empty">暂无数据</td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr key={row.name}>
                    <td className="fault-name-cell">{row.name}</td>
                    <td className="desc-cell" title={row.description}>{row.description || '—'}</td>
                    <td>{row.domain || '—'}</td>
                    <td>{row.data_source || '—'}</td>
                    <td>{row.severity || '—'}</td>
                    <td>{row.category || '—'}</td>
                    <td>{typeof row.confidence === 'number' ? row.confidence.toFixed(2) : '—'}</td>
                    <td className="nowrap">{formatFaultTime(row.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {!loading && total > 0 && (
        <div className="pagination pagination-bottom">
          <button
            type="button"
            className="btn-page"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span className="page-info">
            第 {page} / {totalPages} 页 · 每页最多 {pageSize} 条
          </span>
          <button
            type="button"
            className="btn-page"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

function TriggersAuditPanel() {
  const [items, setItems] = useState<TriggerAuditRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [method, setMethod] = useState('')
  const [ruleNameInput, setRuleNameInput] = useState('')
  const [ruleName, setRuleName] = useState('')
  const [minConfidence, setMinConfidence] = useState(0.8)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setRuleName(ruleNameInput.trim()), 300)
    return () => window.clearTimeout(t)
  }, [ruleNameInput])

  useEffect(() => {
    setPage(1)
  }, [method, ruleName, minConfidence, pageSize])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      min_confidence: String(minConfidence),
    })
    if (method) params.set('method', method)
    if (ruleName) params.set('rule_name', ruleName)
    fetch(`${GRAPH_BASE}/admin/triggers/audit?${params.toString()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (cancelled) return
        setItems(d.items ?? [])
        setTotal(typeof d.total === 'number' ? d.total : 0)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : '加载失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, pageSize, method, ruleName, minConfidence])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="panel fault-table-panel">
      <p className="fault-table-hint">
        该视图展示 <strong>Alert → Fault</strong> 的 <strong>TRIGGERS</strong> 关联审计明细，可按规则名、方法与置信度筛选。
      </p>

      <div className="triggers-toolbar">
        <label className="fault-page-size-label">
          匹配方法
          <select className="fault-page-size" value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="">全部</option>
            <option value="rule">rule</option>
            <option value="fuzzy">fuzzy</option>
          </select>
        </label>
        <label className="fault-page-size-label">
          最低置信度
          <select
            className="fault-page-size"
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          >
            <option value={0.7}>0.70</option>
            <option value={0.8}>0.80</option>
            <option value={0.9}>0.90</option>
          </select>
        </label>
        <input
          className="text-input triggers-rule-search"
          placeholder="按 rule_name 筛选（子串）…"
          value={ruleNameInput}
          onChange={(e) => setRuleNameInput(e.target.value)}
        />
        <label className="fault-page-size-label">
          每页
          <select
            className="fault-page-size"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
          >
            {FAULT_PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>{n} 条</option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="msg-error">{error}</div>}
      {loading && <div className="empty">加载中…</div>}

      {!loading && !error && (
        <div className="fault-table-range">
          共 {total} 条（第 {page} / {totalPages} 页）
        </div>
      )}

      {!loading && total > 0 && (
        <div className="pagination pagination-top">
          <button type="button" className="btn-page" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            上一页
          </button>
          <span className="page-info">第 {page} / {totalPages} 页</span>
          <button type="button" className="btn-page" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
            下一页
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="fault-table-wrap">
          <table className="fault-table">
            <thead>
              <tr>
                <th>alert_id</th>
                <th>fault_name</th>
                <th>confidence</th>
                <th>method</th>
                <th>rule_name</th>
                <th>created_at</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="fault-table-empty">暂无数据</td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr key={row.edge_id}>
                    <td className="nowrap">{row.alert_id}</td>
                    <td>{row.fault_name}</td>
                    <td>{row.confidence.toFixed(2)}</td>
                    <td>{row.method || '—'}</td>
                    <td>{row.rule_name || '—'}</td>
                    <td className="nowrap">{formatFaultTime(row.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DocumentTracePanel() {
  const [documentId, setDocumentId] = useState('')
  const [items, setItems] = useState<Array<{
    document_id: string
    document_vertex: string
    solution_name: string
    fault_names: string[]
    chunk_ref: string
  }>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const search = async () => {
    if (!documentId.trim()) return
    setLoading(true)
    setError('')
    try {
      const resp = await fetch(`${GRAPH_BASE}/graph/document-trace?document_id=${encodeURIComponent(documentId.trim())}`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setItems(data.items ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询失败')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel fault-table-panel">
      <p className="fault-table-hint">
        输入 Dify 的 <strong>document_id</strong>，反查图谱中的 <strong>Solution / Fault</strong> 关联。
      </p>
      <div className="search-row">
        <input
          className="text-input"
          placeholder="输入 document_id（如 45a2de26-...）"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
        />
        <button className="btn-primary" onClick={search} disabled={loading || !documentId.trim()}>
          {loading ? '查询中…' : '反查'}
        </button>
      </div>
      {error && <div className="msg-error">{error}</div>}
      {!loading && items.length === 0 && !error && <div className="empty">暂无结果</div>}
      {!loading && items.length > 0 && (
        <div className="fault-table-wrap">
          <table className="fault-table">
            <thead>
              <tr>
                <th>document_id</th>
                <th>solution_name</th>
                <th>fault_names</th>
                <th>chunk_ref</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={`${it.solution_name}-${idx}`}>
                  <td className="mono">{it.document_id}</td>
                  <td>{it.solution_name}</td>
                  <td>{(it.fault_names ?? []).join('，') || '—'}</td>
                  <td className="mono">{it.chunk_ref || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Graph Visualisation helpers ───────────────────────────────────────────────

const EDGE_LABEL_MAP: Record<string, string> = {
  HAS_SOLUTION:  '关联方案',
  TRIGGERS:      '触发',
  CLASSIFIED_AS: '分类',
  INVOLVES:      '涉及',
  CAUSED_BY:     '导致',
  RESOLVED_BY:   '解决',
}
function fmtEdge(raw: string) { return EDGE_LABEL_MAP[raw] ?? raw ?? '关联' }

const NODE_R: Record<string, number> = {
  Fault: 48, Solution: 40, Alert: 30, Category: 28, Incident: 32,
}
const NODE_CLASS: Record<string, string> = {
  Fault: 'fault-node', Solution: 'solution-node',
  Alert: 'alert-node', Category: 'category-node', Incident: 'incident-node',
}

function initPositions(
  nodes: GraphNode[],
  cx: number,
  cy: number,
): Record<string, { x: number; y: number }> {
  const pos: Record<string, { x: number; y: number }> = {}
  const byType: Record<string, GraphNode[]> = {}
  for (const n of nodes) {
    ;(byType[n.type] = byType[n.type] ?? []).push(n)
  }
  // 主 Fault 居中
  ;(byType['Fault'] ?? []).forEach((n, i) => {
    if (i === 0) pos[n.id] = { x: cx, y: cy }
    else {
      const span = Math.min(Math.PI * 1.2, ((byType['Fault']?.length ?? 1) - 1) * 0.4 + 0.5)
      const a = Math.PI - span / 2 + span * (i - 1) / Math.max((byType['Fault']?.length ?? 2) - 2, 1)
      pos[n.id] = { x: cx + 220 * Math.cos(a), y: cy + 220 * Math.sin(a) }
    }
  })
  // Solutions 第一圈
  const sols = byType['Solution'] ?? []
  sols.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(sols.length, 1) - Math.PI / 2
    pos[n.id] = { x: cx + 155 * Math.cos(a), y: cy + 155 * Math.sin(a) }
  })
  // Alerts 第二圈右侧
  const alerts = byType['Alert'] ?? []
  alerts.forEach((n, i) => {
    const span = Math.min(Math.PI * 1.4, (alerts.length - 1) * 0.38 + 0.5)
    const a = alerts.length === 1 ? 0 : -span / 2 + (span * i) / (alerts.length - 1)
    pos[n.id] = { x: cx + 250 * Math.cos(a), y: cy + 250 * Math.sin(a) }
  })
  // Category 下方
  ;(byType['Category'] ?? []).forEach((n, i) => {
    const a = Math.PI / 2 + (i - ((byType['Category']?.length ?? 1) - 1) / 2) * 0.5
    pos[n.id] = { x: cx + 180 * Math.cos(a), y: cy + 180 * Math.sin(a) }
  })
  return pos
}

interface DragState { id: string; ox: number; oy: number; mx: number; my: number }

function VisualPanel() {
  const [query, setQuery] = useState('')
  const [faults, setFaults] = useState<string[]>([])
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hover, setHover] = useState<string | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const VW = 880, VH = 520
  const CX = VW / 2, CY = VH / 2 - 10

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/faults?page_size=500`)
      .then((r) => r.json())
      .then((d) => setFaults((d.faults ?? []).map((f: string | { name: string }) => typeof f === 'string' ? f : f.name)))
      .catch(() => {})
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true); setError('')
    try {
      const res = await fetch(`${GRAPH_BASE}/graph/visualize?fault_name=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const ns: GraphNode[] = data.nodes ?? []
      const es: GraphEdge[] = data.edges ?? []
      setNodes(ns); setEdges(es)
      setPositions(initPositions(ns, CX, CY))
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询失败')
      setNodes([]); setEdges([])
    } finally { setLoading(false) }
  }

  const svgPoint = (e: React.MouseEvent) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const pt = svg.createSVGPoint()
    pt.x = e.clientX; pt.y = e.clientY
    const ctm = svg.getScreenCTM()
    if (!ctm) return { x: 0, y: 0 }
    const tp = pt.matrixTransform(ctm.inverse())
    return { x: tp.x, y: tp.y }
  }

  const onNodeMouseDown = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    const p = svgPoint(e)
    const pos = positions[id] ?? { x: CX, y: CY }
    dragRef.current = { id, ox: pos.x, oy: pos.y, mx: p.x, my: p.y }
  }, [positions])

  const onSvgMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragRef.current) return
    const { id, ox, oy, mx, my } = dragRef.current
    const p = svgPoint(e)
    setPositions(prev => ({ ...prev, [id]: { x: ox + p.x - mx, y: oy + p.y - my } }))
  }, [])

  const onSvgMouseUp = useCallback(() => { dragRef.current = null }, [])

  return (
    <div className="panel visual-panel">
      <div className="search-row">
        <input
          className="text-input"
          placeholder="输入故障名称，展示多类型关联子图（含告警 / 分类 / 邻近故障）…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          list="fault-list-visual"
        />
        <datalist id="fault-list-visual">
          {faults.map((f) => <option key={f} value={f} />)}
        </datalist>
        <button className="btn-primary" onClick={search} disabled={loading}>
          {loading ? '加载中…' : '生成图谱'}
        </button>
      </div>

      {error && <div className="msg-error">{error}</div>}
      {nodes.length === 0 && !loading && (
        <div className="empty">输入故障名称后点击「生成图谱」，节点可自由拖动</div>
      )}

      {nodes.length > 0 && (
        <div className="graph-canvas-wrap">
          <svg
            ref={svgRef}
            className="graph-canvas graph-canvas--draggable"
            viewBox={`0 0 ${VW} ${VH}`}
            role="img"
            aria-label="故障关联子图"
            onMouseMove={onSvgMouseMove}
            onMouseUp={onSvgMouseUp}
            onMouseLeave={onSvgMouseUp}
          >
            <defs>
              <filter id="nodeGlow2">
                <feDropShadow dx="0" dy="2" stdDeviation="5" floodColor="#000" floodOpacity="0.4" />
              </filter>
              <marker id="arrowFwd" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10z" className="edge-arrow-head" />
              </marker>
            </defs>

            {/* Edges */}
            <g>
              {edges.map((e) => {
                const src = positions[String(e.source)]
                const tgt = positions[String(e.target)]
                if (!src || !tgt) return null
                const rS = NODE_R[nodes.find(n => String(n.id) === String(e.source))?.type ?? 'Fault'] ?? 40
                const rT = NODE_R[nodes.find(n => String(n.id) === String(e.target))?.type ?? 'Solution'] ?? 36
                const dx = tgt.x - src.x, dy = tgt.y - src.y
                const len = Math.hypot(dx, dy) || 1
                const ux = dx / len, uy = dy / len
                const x1 = src.x + ux * rS, y1 = src.y + uy * rS
                const x2 = tgt.x - ux * rT, y2 = tgt.y - uy * rT
                const lx = (x1 + x2) / 2 + (-uy) * 16
                const ly = (y1 + y2) / 2 + ux * 16
                const lbl = fmtEdge(e.label ?? '')
                const hot = hover === String(e.source) || hover === String(e.target)
                return (
                  <g key={e.id} className={`visual-spoke ${hot ? 'visual-spoke--hot' : ''}`}>
                    <line x1={x1} y1={y1} x2={x2} y2={y2} className="edge-hit" />
                    <line x1={x1} y1={y1} x2={x2} y2={y2}
                      className="edge-line" markerEnd="url(#arrowFwd)" />
                    <text x={lx} y={ly} className="edge-label-inline">{lbl}</text>
                  </g>
                )
              })}
            </g>

            {/* Nodes */}
            <g>
              {nodes.map((n) => {
                const pos = positions[n.id] ?? { x: CX, y: CY }
                const r   = NODE_R[n.type] ?? 36
                const cls = NODE_CLASS[n.type] ?? 'fault-node'
                const hot = hover === n.id
                const lbl = n.label.length > 14 ? n.label.slice(0, 13) + '…' : n.label
                return (
                  <g key={n.id}
                    className={`visual-node-group ${hot ? 'visual-node-group--hot' : ''}`}
                    style={{ cursor: 'grab' }}
                    onMouseEnter={() => setHover(n.id)}
                    onMouseLeave={() => setHover(null)}
                    onMouseDown={(e) => onNodeMouseDown(e, n.id)}
                  >
                    <title>{`[${n.type}] ${n.label}`}</title>
                    <circle cx={pos.x} cy={pos.y} r={r} className={cls} filter="url(#nodeGlow2)" />
                    <text x={pos.x} y={pos.y}
                      className={`node-label ${r < 36 ? 'node-label--xs' : r < 44 ? 'node-label--sm' : ''}`}>
                      {lbl}
                    </text>
                  </g>
                )
              })}
            </g>

            {/* Legend */}
            <g pointerEvents="none">
              {[
                { cls: 'fault-node',    lbl: '故障' },
                { cls: 'solution-node', lbl: '方案' },
                { cls: 'alert-node',    lbl: '告警' },
                { cls: 'category-node', lbl: '分类' },
              ].map(({ cls, lbl }, i) => (
                <g key={cls} transform={`translate(${14 + i * 92}, ${VH - 34})`}>
                  <circle cx={10} cy={8} r={8} className={`${cls} legend-dot`} />
                  <text x={24} y={13} className="visual-legend-text">{lbl}</text>
                </g>
              ))}
              <text x={VW - 14} y={VH - 22} className="visual-legend-text"
                textAnchor="end" style={{ fontSize: '0.68rem', opacity: 0.45 }}>
                节点可拖动
              </text>
            </g>
          </svg>
        </div>
      )}
    </div>
  )
}


function QueryPanel() {
  const [query, setQuery]       = useState('')
  const [faults, setFaults]     = useState<string[]>([])
  const [results, setResults]   = useState<Solution[] | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/faults?page_size=500`)
      .then((r) => r.json())
      .then((d) => setFaults((d.faults ?? []).map((f: string | { name: string }) => typeof f === 'string' ? f : f.name)))
      .catch(() => {})
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true); setError(''); setResults(null)
    try {
      const res = await fetch(`${GRAPH_BASE}/graph/query?fault_name=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setResults(data.solutions ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="search-row">
        <input
          className="text-input"
          placeholder="输入故障名称…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          list="fault-list"
        />
        <datalist id="fault-list">
          {faults.map((f) => <option key={f} value={f} />)}
        </datalist>
        <button className="btn-primary" onClick={search} disabled={loading}>
          {loading ? '查询中…' : '查询'}
        </button>
      </div>

      {error && <div className="msg-error">{error}</div>}

      {results !== null && (
        results.length === 0
          ? <div className="empty">未找到相关解决方案</div>
          : (
            <div className="result-list">
              {results.map((s, i) => (
                <div key={s.id} className="result-card">
                  <div className="result-num">#{i + 1}</div>
                  <div className="result-body">
                    <div className="result-name">{s.name}</div>
                    <div className="result-desc">{s.description}</div>
                  </div>
                </div>
              ))}
            </div>
          )
      )}
    </div>
  )
}

function AddPanel() {
  const { writeHeaders } = useRole()
  const [fault, setFault]       = useState('')
  const [solName, setSolName]   = useState('')
  const [solDesc, setSolDesc]   = useState('')
  const [status, setStatus]     = useState<'idle' | 'ok' | 'dup' | 'err'>('idle')
  const [loading, setLoading]   = useState(false)
  const [errMsg, setErrMsg]     = useState('')

  const submit = async () => {
    if (!fault.trim() || !solName.trim() || !solDesc.trim()) return
    setLoading(true); setStatus('idle')
    try {
      const res = await fetch(`${GRAPH_BASE}/graph/add`, {
        method: 'POST',
        headers: writeHeaders(),
        body: JSON.stringify({ fault_name: fault, solution_name: solName, solution_description: solDesc }),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(e.detail ?? '请求失败')
      }
      const data = await res.json()
      setStatus(data.edge_status === 'exists' ? 'dup' : 'ok')
      if (data.edge_status !== 'exists') { setFault(''); setSolName(''); setSolDesc('') }
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : '录入失败')
      setStatus('err')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="form">
        <label className="form-label">故障名称</label>
        <input className="text-input" placeholder="如：Kafka 消费积压" value={fault} onChange={(e) => setFault(e.target.value)} />

        <label className="form-label">解决方案名称</label>
        <input className="text-input" placeholder="如：调整消费者线程数" value={solName} onChange={(e) => setSolName(e.target.value)} />

        <label className="form-label">方案详情</label>
        <textarea
          className="text-input textarea"
          placeholder="详细描述解决步骤…"
          value={solDesc}
          onChange={(e) => setSolDesc(e.target.value)}
          rows={4}
        />

        <button
          className="btn-primary"
          onClick={submit}
          disabled={loading || !fault.trim() || !solName.trim() || !solDesc.trim()}
        >
          {loading ? '录入中…' : '录入'}
        </button>

        {status === 'ok'  && <div className="msg-ok">✅ 录入成功</div>}
        {status === 'dup' && <div className="msg-warn">⚠️ 该关联关系已存在</div>}
        {status === 'err' && <div className="msg-error">❌ {errMsg}</div>}
      </div>
    </div>
  )
}
