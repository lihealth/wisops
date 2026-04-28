import { useState, useEffect } from 'react'
import './GraphPage.css'

const GRAPH_BASE = '/graph-api'

interface Solution { id: string; name: string; description: string }

export default function GraphPage() {
  const [tab, setTab] = useState<'query' | 'add'>('query')

  return (
    <div className="graph-page">
      <div className="graph-header">
        <span className="graph-title">故障图谱管理</span>
        <div className="graph-tabs">
          <button className={tab === 'query' ? 'tab active' : 'tab'} onClick={() => setTab('query')}>查询方案</button>
          <button className={tab === 'add'   ? 'tab active' : 'tab'} onClick={() => setTab('add')}>录入故障</button>
        </div>
      </div>
      <div className="graph-body">
        {tab === 'query' ? <QueryPanel /> : <AddPanel />}
      </div>
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
