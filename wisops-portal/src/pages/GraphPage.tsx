import { useState, useEffect } from 'react'
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

interface Solution { id: string; name: string; description: string }
interface GraphNode { id: string; label: string; type: 'Fault' | 'Solution' }
interface GraphEdge { id: string; source: string; target: string; label: string }

export default function GraphPage() {
  const [tab, setTab] = useState<'query' | 'add' | 'visual' | 'catalog'>('query')

  return (
    <div className="graph-page">
      <div className="graph-header">
        <span className="graph-title">故障图谱管理</span>
        <div className="graph-tabs">
          <button className={tab === 'query' ? 'tab active' : 'tab'} onClick={() => setTab('query')}>查询方案</button>
          <button className={tab === 'visual' ? 'tab active' : 'tab'} onClick={() => setTab('visual')}>图谱可视化</button>
          <button className={tab === 'catalog' ? 'tab active' : 'tab'} onClick={() => setTab('catalog')}>故障列表</button>
          <button className={tab === 'add'   ? 'tab active' : 'tab'} onClick={() => setTab('add')}>录入故障</button>
        </div>
      </div>
      <div className="graph-body">
        {tab === 'query' && <QueryPanel />}
        {tab === 'visual' && <VisualPanel />}
        {tab === 'catalog' && <FaultTablePanel />}
        {tab === 'add' && <AddPanel />}
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

function formatEdgeRelationLabel(raw: string): string {
  const t = (raw || '').trim()
  if (t === 'HAS_SOLUTION' || t === '') return '关联方案'
  return t
}

/** 从圆心连线缩短到圆周，便于画边与标签 */
function shortenChord(
  cx: number,
  cy: number,
  tx: number,
  ty: number,
  fromR: number,
  toR: number,
) {
  const dx = tx - cx
  const dy = ty - cy
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  return {
    x1: cx + ux * fromR,
    y1: cy + uy * fromR,
    x2: tx - ux * toR,
    y2: ty - uy * toR,
    ux,
    uy,
    px: -uy,
    py: ux,
  }
}

function VisualPanel() {
  const [query, setQuery] = useState('')
  const [faults, setFaults] = useState<string[]>([])
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hoverSpoke, setHoverSpoke] = useState<string | null>(null)
  const [hoverFault, setHoverFault] = useState(false)

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/faults`)
      .then((r) => r.json())
      .then((d) => setFaults(d.faults ?? []))
      .catch(() => {})
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${GRAPH_BASE}/graph/visualize?fault_name=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setNodes(data.nodes ?? [])
      setEdges(data.edges ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '查询失败')
      setNodes([])
      setEdges([])
    } finally {
      setLoading(false)
    }
  }

  const fault = nodes.find((n) => n.type === 'Fault')
  const solutions = nodes.filter((n) => n.type === 'Solution')
  const vbW = 820
  const vbH = 480
  const centerX = vbW / 2
  const centerY = vbH / 2 - 10
  const radius = Math.min(168, 110 + solutions.length * 12)
  const faultR = 56
  const solR = 46
  const labelOffset = 36

  return (
    <div className="panel visual-panel">
      <div className="search-row">
        <input
          className="text-input"
          placeholder="输入故障名称，展示关联子图…"
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
      {!fault && !loading && <div className="empty">输入故障名称后点击“生成图谱”</div>}

      {fault && (
        <div className="graph-canvas-wrap">
          <p className="visual-legend-hint">悬停节点或连线可高亮；边标签已外移避免与圆重叠。</p>
          <svg
            className="graph-canvas"
            viewBox={`0 0 ${vbW} ${vbH}`}
            role="img"
            aria-label="故障关联子图"
          >
            <defs>
              <linearGradient id="faultGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#4f46e5" />
              </linearGradient>
              <linearGradient id="solGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#14b8a6" />
                <stop offset="100%" stopColor="#0d9488" />
              </linearGradient>
              <filter id="nodeGlow" x="-40%" y="-40%" width="180%" height="180%">
                <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#000" floodOpacity="0.35" />
              </filter>
              <marker
                id="arrowHasSol"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" className="edge-arrow-head" />
              </marker>
            </defs>

            <g key={fault.id} className="visual-graph-root">
              {solutions.map((s, i) => {
                const angle = (Math.PI * 2 * i) / Math.max(solutions.length, 1)
                const x = centerX + radius * Math.cos(angle)
                const y = centerY + radius * Math.sin(angle)
                const chord = shortenChord(centerX, centerY, x, y, faultR, solR)
                const mx = (chord.x1 + chord.x2) / 2
                const my = (chord.y1 + chord.y2) / 2
                const lx = mx + chord.px * labelOffset
                const ly = my + chord.py * labelOffset
                const edge = edges.find((e) => String(e.source) === String(fault.id) && String(e.target) === String(s.id))
                const rel = formatEdgeRelationLabel(edge?.label ?? '')
                const hot = hoverSpoke === s.id
                const tw = Math.min(220, Math.max(56, rel.length * 12 + 16))

                return (
                  <g
                    key={s.id}
                    className={`visual-spoke ${hot ? 'visual-spoke--hot' : ''}`}
                    onMouseEnter={() => setHoverSpoke(s.id)}
                    onMouseLeave={() => setHoverSpoke(null)}
                  >
                    <title>{`${rel} → ${s.label}`}</title>
                    <line
                      x1={chord.x1}
                      y1={chord.y1}
                      x2={chord.x2}
                      y2={chord.y2}
                      className="edge-hit"
                    />
                    <line
                      x1={chord.x1}
                      y1={chord.y1}
                      x2={chord.x2}
                      y2={chord.y2}
                      className="edge-line"
                      markerEnd="url(#arrowHasSol)"
                    />
                    <g className="edge-label-group" pointerEvents="none">
                      <rect
                        x={lx - tw / 2}
                        y={ly - 12}
                        width={tw}
                        height={24}
                        rx={8}
                        className="edge-label-bg"
                      />
                      <text x={lx} y={ly} className="edge-label">
                        {rel}
                      </text>
                    </g>
                    <circle cx={x} cy={y} r={solR} className="solution-node" filter="url(#nodeGlow)" />
                    <text
                      x={x}
                      y={y}
                      className={`node-label ${s.label.length > 16 ? 'node-label--sm' : ''}`}
                    >
                      {s.label}
                    </text>
                  </g>
                )
              })}

              <g
                className={`visual-fault-hub ${hoverFault ? 'visual-fault-hub--hot' : ''}`}
                onMouseEnter={() => setHoverFault(true)}
                onMouseLeave={() => setHoverFault(false)}
              >
                <title>{fault.label}</title>
                <circle cx={centerX} cy={centerY} r={faultR} className="fault-node" filter="url(#nodeGlow)" />
                <text
                  x={centerX}
                  y={centerY}
                  className={`node-label node-label-main ${fault.label.length > 14 ? 'node-label-main--sm' : ''}`}
                >
                  {fault.label}
                </text>
              </g>
            </g>

            <g className="visual-legend" pointerEvents="none">
              <rect x={16} y={vbH - 44} width={268} height={32} rx={8} className="visual-legend-box" />
              <circle cx={36} cy={vbH - 28} r={8} className="fault-node legend-dot" />
              <text x={50} y={vbH - 24} className="visual-legend-text">故障（Fault）</text>
              <circle cx={138} cy={vbH - 28} r={8} className="solution-node legend-dot" />
              <text x={152} y={vbH - 24} className="visual-legend-text">方案（Solution）</text>
              <line x1={230} y1={vbH - 28} x2={252} y2={vbH - 28} className="edge-line legend-line" />
              <text x={258} y={vbH - 24} className="visual-legend-text">关系</text>
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
    fetch(`${GRAPH_BASE}/graph/faults`)
      .then((r) => r.json())
      .then((d) => setFaults(d.faults ?? []))
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
        headers: { 'Content-Type': 'application/json' },
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
