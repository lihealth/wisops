import { useState, useEffect, useRef } from 'react'
import { useRole } from '../RoleContext'
import './ExtractPage.css'

const GRAPH_BASE = '/graph-api'

interface Job {
  job_id: string
  source_hint: string
  status: 'pending' | 'running' | 'done' | 'failed'
  created_at: number
  candidate_count: number
  error?: string
}

interface QueueItem {
  id: string
  job_id: string
  source_hint: string
  fault_name: string
  solution_name: string
  solution_description: string
  confidence: number
  status: 'pending' | 'approved' | 'rejected'
  created_at: number
}

interface ApproveResult {
  status: string
  item_id: string
  dify_sync?: {
    ok?: boolean
    document_id?: string
    message?: string
  }
  graph_document_link?: {
    ok?: boolean
    message?: string
    document_vertex_name?: string
  }
}

interface DocLinkItem {
  item_id: string
  job_id: string
  fault_name: string
  solution_name: string
  document_id: string
  created_at: number
  graph_document_link?: {
    ok?: boolean
    message?: string
    document_vertex_name?: string
  }
}

export default function ExtractPage() {
  const [tab, setTab] = useState<'submit' | 'jobs' | 'queue' | 'trace'>('submit')
  const [latestApprove, setLatestApprove] = useState<ApproveResult | null>(null)
  return (
    <div className="extract-page">
      <div className="extract-header">
        <span className="extract-title">知识抽取</span>
        <div className="extract-tabs">
          <button className={tab === 'submit' ? 'tab active' : 'tab'} onClick={() => setTab('submit')}>提交文档</button>
          <button className={tab === 'jobs'   ? 'tab active' : 'tab'} onClick={() => setTab('jobs')}>任务列表</button>
          <button className={tab === 'queue'  ? 'tab active' : 'tab'} onClick={() => setTab('queue')}>审核队列</button>
          <button className={tab === 'trace'  ? 'tab active' : 'tab'} onClick={() => setTab('trace')}>文档追溯</button>
        </div>
      </div>
      <div className="extract-body">
        {tab === 'submit' && <SubmitPanel onSubmitted={() => setTab('jobs')} />}
        {tab === 'jobs'   && <JobsPanel onGoQueue={() => setTab('queue')} />}
        {tab === 'queue'  && <QueuePanel onApproved={(r) => { setLatestApprove(r); setTab('trace') }} />}
        {tab === 'trace'  && <DocTracePanel latestApprove={latestApprove} />}
      </div>
    </div>
  )
}

function SubmitPanel({ onSubmitted }: { onSubmitted: () => void }) {
  const { writeHeaders } = useRole()
  const [text, setText]           = useState('')
  const [sourceHint, setSource]   = useState('')
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState<{ job_id: string } | null>(null)
  const [error, setError]         = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setSource(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => setText(ev.target?.result as string ?? '')
    reader.readAsText(file, 'utf-8')
  }

  const submit = async () => {
    if (!text.trim()) return
    setLoading(true); setError(''); setResult(null)
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/submit`, {
        method: 'POST',
        headers: writeHeaders(),
        body: JSON.stringify({ text, source_hint: sourceHint || '手动粘贴' }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setResult(data)
      setText(''); setSource('')
      setTimeout(onSubmitted, 1500)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="section-title">上传或粘贴运维文档，系统将自动抽取故障–方案知识</div>

      <div className="upload-row">
        <button className="btn-outline" onClick={() => fileRef.current?.click()}>
          选择文件（txt / md）
        </button>
        <input ref={fileRef} type="file" accept=".txt,.md,.log" style={{ display: 'none' }} onChange={handleFile} />
        {sourceHint && <span className="file-name">{sourceHint}</span>}
      </div>

      <textarea
        className="text-area"
        placeholder="或在此处直接粘贴运维文档内容，如 SOP、故障记录、Runbook..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={12}
      />

      <div className="form-row">
        <input
          className="text-input"
          placeholder="来源说明（可选，如：nginx_runbook.md / 工单#1234）"
          value={sourceHint}
          onChange={(e) => setSource(e.target.value)}
        />
        <button className="btn-primary" onClick={submit} disabled={loading || !text.trim()}>
          {loading ? '抽取中…' : '提交抽取'}
        </button>
      </div>

      {result && <div className="msg-ok">✅ 任务已提交，Job ID：{result.job_id}，正在跳转任务列表…</div>}
      {error  && <div className="msg-error">❌ {error}</div>}

      <div className="tip-box">
        <div className="tip-title">抽取说明</div>
        <ul className="tip-list">
          <li>系统将调用 AI 自动从文本中识别故障现象和对应解决方案</li>
          <li>抽取结果需经人工审核后才会写入图谱</li>
          <li>建议每次提交单一主题的文档（单个 SOP 或故障记录），提高准确率</li>
          <li>支持文件上传或直接粘贴，最大约 50000 字符</li>
        </ul>
      </div>
    </div>
  )
}

function JobsPanel({ onGoQueue }: { onGoQueue: () => void }) {
  const [jobs, setJobs]     = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const fetchJobs = async () => {
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/jobs`)
      const data = await resp.json()
      setJobs(data.jobs ?? [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  useEffect(() => {
    fetchJobs()
    const t = setInterval(fetchJobs, 5000)
    return () => clearInterval(t)
  }, [])

  const statusBadge = (s: Job['status']) => {
    const map: Record<string, string> = {
      pending: 'badge-gray', running: 'badge-blue',
      done: 'badge-green', failed: 'badge-red'
    }
    const label: Record<string, string> = {
      pending: '待处理', running: '抽取中', done: '完成', failed: '失败'
    }
    return <span className={`badge ${map[s] ?? 'badge-gray'}`}>{label[s] ?? s}</span>
  }

  if (loading) return <div className="loading">加载中…</div>

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="section-title">抽取任务列表</span>
        <button className="btn-outline" onClick={fetchJobs}>刷新</button>
        <button className="btn-primary" onClick={onGoQueue}>查看审核队列 →</button>
      </div>

      {jobs.length === 0 ? (
        <div className="empty">暂无任务，请先提交文档</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Job ID</th><th>来源</th><th>状态</th><th>候选条数</th><th>提交时间</th></tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id}>
                <td className="mono">{j.job_id}</td>
                <td>{j.source_hint}</td>
                <td>{statusBadge(j.status)}</td>
                <td>{j.candidate_count}</td>
                <td>{new Date(j.created_at).toLocaleString('zh-CN')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function QueuePanel({ onApproved }: { onApproved: (r: ApproveResult) => void }) {
  const { can, writeHeaders } = useRole()
  const canApprove = can('approve_extract')
  const [items, setItems]     = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [opLoading, setOp]    = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchNotice, setBatchNotice] = useState<{ text: string; ok: boolean } | null>(null)

  const fetchQueue = async () => {
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/queue?status=pending`)
      const data = await resp.json()
      setItems(data.items ?? [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  useEffect(() => { fetchQueue() }, [])

  useEffect(() => {
    const ids = new Set(items.map((i) => i.id))
    setSelected((prev) => {
      const next = new Set<string>()
      prev.forEach((id) => { if (ids.has(id)) next.add(id) })
      return next
    })
  }, [items])

  const toggleSel = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAllPending = () => {
    setSelected(new Set(items.map((i) => i.id)))
  }

  const act = async (id: string, action: 'approve' | 'reject') => {
    setOp(id)
    setBatchNotice(null)
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/queue/${id}/${action}`, { method: 'POST', headers: writeHeaders() })
      if (action === 'approve' && resp.ok) {
        const data = await resp.json()
        onApproved(data as ApproveResult)
      }
      setItems((prev) => prev.filter((it) => it.id !== id))
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch { /* ignore */ } finally { setOp(null) }
  }

  const batchAct = async (action: 'approve' | 'reject') => {
    const ids = Array.from(selected)
    if (ids.length === 0 || batchLoading) return
    setBatchLoading(true)
    setBatchNotice(null)
    const path = action === 'approve' ? 'batch-approve' : 'batch-reject'
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/queue/${path}`, {
        method: 'POST',
        headers: writeHeaders(),
        body: JSON.stringify({ item_ids: ids }),
      })
      let data: { succeeded?: number; failed?: number; detail?: string; message?: string } = {}
      try { data = await resp.json() } catch { /* ignore */ }
      if (!resp.ok) {
        const msg = typeof data.detail === 'string' ? data.detail : (data.message || `HTTP ${resp.status}`)
        throw new Error(msg)
      }
      setBatchNotice({
        ok: true,
        text: `批量${action === 'approve' ? '通过' : '拒绝'}完成：成功 ${data.succeeded ?? 0}，未成功 ${data.failed ?? 0}`,
      })
      setSelected(new Set())
      await fetchQueue()
    } catch (e) {
      setBatchNotice({ ok: false, text: e instanceof Error ? e.message : '批量操作失败' })
    } finally {
      setBatchLoading(false)
    }
  }

  if (loading) return <div className="loading">加载中…</div>

  const selCount = selected.size
  const busy = batchLoading || opLoading !== null

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="section-title">待审核条目（{items.length} 条）</span>
        <button className="btn-outline" onClick={fetchQueue} disabled={busy}>刷新</button>
      </div>

      {items.length > 0 && canApprove && (
        <div className="queue-batch-bar">
          <label className="queue-check-label">
            <input
              type="checkbox"
              checked={selCount > 0 && selCount === items.length}
              ref={(el) => {
                if (!el) return
                el.indeterminate = selCount > 0 && selCount < items.length
              }}
              onChange={(e) => { e.target.checked ? selectAllPending() : setSelected(new Set()) }}
              disabled={busy}
            />
            <span>全选</span>
          </label>
          <span className="queue-batch-hint">已选 {selCount} 条</span>
          <button
            type="button"
            className="btn-batch-approve"
            disabled={selCount === 0 || busy}
            onClick={() => batchAct('approve')}
          >
            ✅ 批量通过
          </button>
          <button
            type="button"
            className="btn-batch-reject"
            disabled={selCount === 0 || busy}
            onClick={() => batchAct('reject')}
          >
            ❌ 批量拒绝
          </button>
        </div>
      )}
      {items.length > 0 && !canApprove && (
        <div className="msg-error" style={{ fontSize: '0.82rem' }}>🔒 当前角色无审核权限，仅可查看待审条目</div>
      )}
      {batchNotice && <div className={batchNotice.ok ? 'msg-ok' : 'msg-error'}>{batchNotice.text}</div>}

      {items.length === 0 ? (
        <div className="empty">队列为空，暂无待审核条目</div>
      ) : (
        <div className="queue-list">
          {items.map((it) => (
            <div key={it.id} className="queue-card">
              <div className="queue-meta">
                <label className="queue-check-label queue-check-inline">
                  <input
                    type="checkbox"
                    checked={selected.has(it.id)}
                    onChange={() => toggleSel(it.id)}
                    disabled={busy}
                  />
                </label>
                <span className="mono">#{it.id}</span>
                <span className="conf-badge">置信度 {Math.round(it.confidence * 100)}%</span>
                <span className="source-tag">来源：{it.source_hint}</span>
              </div>
              <div className="queue-fields">
                <div>
                  <span className="field-label">故障名</span>
                  <span className="field-val">{it.fault_name || '（未识别）'}</span>
                </div>
                <div>
                  <span className="field-label">方案名</span>
                  <span className="field-val">{it.solution_name || '（未识别）'}</span>
                </div>
                {it.solution_description && (
                  <div>
                    <span className="field-label">方案描述</span>
                    <span className="field-val desc">{it.solution_description}</span>
                  </div>
                )}
              </div>
              {canApprove && (
                <div className="queue-actions">
                  <button
                    className="btn-approve"
                    onClick={() => act(it.id, 'approve')}
                    disabled={busy || opLoading === it.id}
                  >
                    ✅ 通过入库
                  </button>
                  <button
                    className="btn-reject"
                    onClick={() => act(it.id, 'reject')}
                    disabled={busy || opLoading === it.id}
                  >
                    ❌ 拒绝
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DocTracePanel({ latestApprove }: { latestApprove: ApproveResult | null }) {
  const [items, setItems] = useState<DocLinkItem[]>([])
  const [docId, setDocId] = useState('')
  const [jobId, setJobId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchLinks = async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ limit: '100' })
      if (jobId.trim()) params.set('job_id', jobId.trim())
      const resp = await fetch(`${GRAPH_BASE}/extract/doc-links?${params.toString()}`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      let rows: DocLinkItem[] = data.items ?? []
      if (docId.trim()) {
        const needle = docId.trim().toLowerCase()
        rows = rows.filter((r) => String(r.document_id || '').toLowerCase().includes(needle))
      }
      setItems(rows)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLinks() }, [])

  const copyText = async (text: string) => {
    if (!text) return
    try { await navigator.clipboard.writeText(text) } catch { /* ignore */ }
  }

  return (
    <div className="panel doc-trace-panel">
      <div className="panel-toolbar">
        <span className="section-title">文档追溯索引</span>
        <button className="btn-outline" onClick={fetchLinks}>刷新</button>
      </div>
      {latestApprove && (
        <div className="msg-ok">
          最近一次通过：document_id = {latestApprove.dify_sync?.document_id || '—'}，
          graph_link = {latestApprove.graph_document_link?.message || '—'}
        </div>
      )}
      <div className="form-row">
        <input
          className="text-input"
          placeholder="按 document_id 过滤（支持子串）"
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
        />
        <input
          className="text-input"
          placeholder="按 job_id 过滤（精确匹配）"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
        />
        <button className="btn-primary" onClick={fetchLinks}>查询</button>
      </div>

      {error && <div className="msg-error">❌ {error}</div>}
      {loading ? (
        <div className="loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="empty">暂无追溯数据</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>item_id</th><th>job_id</th><th>document_id</th><th>故障/方案</th><th>图谱映射</th><th>操作</th></tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={`${it.item_id}-${it.document_id}`}>
                <td className="mono">{it.item_id}</td>
                <td className="mono">{it.job_id}</td>
                <td className="mono">{it.document_id || '—'}</td>
                <td>{it.fault_name} / {it.solution_name}</td>
                <td>{it.graph_document_link?.message || '—'}</td>
                <td>
                  <button className="btn-outline btn-sm" onClick={() => copyText(it.document_id)}>复制 document_id</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
