import { useState, useEffect, useRef } from 'react'
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

export default function ExtractPage() {
  const [tab, setTab] = useState<'submit' | 'jobs' | 'queue'>('submit')
  return (
    <div className="extract-page">
      <div className="extract-header">
        <span className="extract-title">知识抽取</span>
        <div className="extract-tabs">
          <button className={tab === 'submit' ? 'tab active' : 'tab'} onClick={() => setTab('submit')}>提交文档</button>
          <button className={tab === 'jobs'   ? 'tab active' : 'tab'} onClick={() => setTab('jobs')}>任务列表</button>
          <button className={tab === 'queue'  ? 'tab active' : 'tab'} onClick={() => setTab('queue')}>审核队列</button>
        </div>
      </div>
      <div className="extract-body">
        {tab === 'submit' && <SubmitPanel onSubmitted={() => setTab('jobs')} />}
        {tab === 'jobs'   && <JobsPanel onGoQueue={() => setTab('queue')} />}
        {tab === 'queue'  && <QueuePanel />}
      </div>
    </div>
  )
}

function SubmitPanel({ onSubmitted }: { onSubmitted: () => void }) {
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
        headers: { 'Content-Type': 'application/json' },
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

function QueuePanel() {
  const [items, setItems]     = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [opLoading, setOp]    = useState<string | null>(null)

  const fetchQueue = async () => {
    try {
      const resp = await fetch(`${GRAPH_BASE}/extract/queue?status=pending`)
      const data = await resp.json()
      setItems(data.items ?? [])
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  useEffect(() => { fetchQueue() }, [])

  const act = async (id: string, action: 'approve' | 'reject') => {
    setOp(id)
    try {
      await fetch(`${GRAPH_BASE}/extract/queue/${id}/${action}`, { method: 'POST' })
      setItems((prev) => prev.filter((it) => it.id !== id))
    } catch { /* ignore */ } finally { setOp(null) }
  }

  if (loading) return <div className="loading">加载中…</div>

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <span className="section-title">待审核条目（{items.length} 条）</span>
        <button className="btn-outline" onClick={fetchQueue}>刷新</button>
      </div>

      {items.length === 0 ? (
        <div className="empty">队列为空，暂无待审核条目</div>
      ) : (
        <div className="queue-list">
          {items.map((it) => (
            <div key={it.id} className="queue-card">
              <div className="queue-meta">
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
              <div className="queue-actions">
                <button
                  className="btn-approve"
                  onClick={() => act(it.id, 'approve')}
                  disabled={opLoading === it.id}
                >
                  ✅ 通过入库
                </button>
                <button
                  className="btn-reject"
                  onClick={() => act(it.id, 'reject')}
                  disabled={opLoading === it.id}
                >
                  ❌ 拒绝
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
