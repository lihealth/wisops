import { useState, useEffect } from 'react'
import './SopPage.css'

const GRAPH_BASE = '/graph-api'

interface SOP {
  title: string
  steps: string[]
  version: string
  author: string
  data_source: string
}

export default function SopPage() {
  const [tab, setTab] = useState<'list' | 'create'>('list')
  const [editSop, setEditSop] = useState<SOP | null>(null)

  const onEdit = (sop: SOP) => { setEditSop(sop); setTab('create') }
  const onSaved = () => { setEditSop(null); setTab('list') }

  return (
    <div className="sop-page">
      <div className="sop-header">
        <span className="sop-title">SOP 管理</span>
        <div className="sop-tabs">
          <button className={tab === 'list'   ? 'tab active' : 'tab'} onClick={() => { setTab('list');   setEditSop(null) }}>SOP 列表</button>
          <button className={tab === 'create' ? 'tab active' : 'tab'} onClick={() => setTab('create')}>
            {editSop ? '编辑 SOP' : '新建 SOP'}
          </button>
        </div>
      </div>
      <div className="sop-body">
        {tab === 'list'   && <SopList onEdit={onEdit} onCreate={() => setTab('create')} />}
        {tab === 'create' && <SopForm initial={editSop} onSaved={onSaved} />}
      </div>
    </div>
  )
}

function SopList({ onEdit, onCreate }: { onEdit: (s: SOP) => void; onCreate: () => void }) {
  const [sops, setSops]       = useState<SOP[]>([])
  const [filter, setFilter]   = useState('')
  const [loading, setLoading] = useState(true)
  const [expand, setExpand]   = useState<string | null>(null)

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/sop`)
      .then((r) => r.json())
      .then((d) => setSops(d.sops ?? []))
      .finally(() => setLoading(false))
  }, [])

  const filtered = filter
    ? sops.filter((s) => s.title.includes(filter) || s.author.includes(filter))
    : sops

  if (loading) return <div className="loading">加载中…</div>

  return (
    <div className="panel">
      <div className="list-toolbar">
        <input
          className="text-input"
          placeholder="搜索 SOP 标题或作者…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button className="btn-primary" onClick={onCreate}>+ 新建 SOP</button>
      </div>

      {filtered.length === 0 ? (
        <div className="empty">暂无 SOP，点击「新建 SOP」创建第一条</div>
      ) : (
        <div className="sop-list">
          {filtered.map((sop) => (
            <div key={sop.title} className="sop-card">
              <div className="sop-card-header" onClick={() => setExpand(expand === sop.title ? null : sop.title)}>
                <div className="sop-card-left">
                  <span className="sop-icon">📋</span>
                  <div>
                    <div className="sop-card-title">{sop.title}</div>
                    <div className="sop-card-meta">
                      版本 {sop.version}
                      {sop.author && <> · {sop.author}</>}
                      · <span className="source-tag">{sop.data_source}</span>
                      · {sop.steps.length} 步骤
                    </div>
                  </div>
                </div>
                <div className="sop-card-right">
                  <button className="btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(sop) }}>编辑</button>
                  <span className="expand-icon">{expand === sop.title ? '▲' : '▼'}</span>
                </div>
              </div>

              {expand === sop.title && (
                <div className="sop-steps">
                  <div className="steps-title">处置步骤</div>
                  <ol className="steps-list">
                    {sop.steps.map((step, i) => (
                      <li key={i} className="step-item">{step}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SopForm({ initial, onSaved }: { initial: SOP | null; onSaved: () => void }) {
  const [faults, setFaults]     = useState<string[]>([])
  const [faultName, setFault]   = useState('')
  const [title, setTitle]       = useState(initial?.title ?? '')
  const [steps, setSteps]       = useState<string[]>(initial?.steps ?? [''])
  const [version, setVersion]   = useState(initial?.version ?? '1.0')
  const [author, setAuthor]     = useState(initial?.author ?? '')
  const [loading, setLoading]   = useState(false)
  const [success, setSuccess]   = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/faults?page_size=500`)
      .then((r) => r.json())
      .then((d) => setFaults((d.faults ?? []).map((f: string | { name: string }) => typeof f === 'string' ? f : f.name)))
      .catch(() => {})
  }, [])

  const addStep    = () => setSteps((p) => [...p, ''])
  const removeStep = (i: number) => setSteps((p) => p.filter((_, idx) => idx !== i))
  const updateStep = (i: number, val: string) =>
    setSteps((p) => p.map((s, idx) => idx === i ? val : s))

  const submit = async () => {
    const validSteps = steps.filter((s) => s.trim())
    if (!title.trim() || !faultName.trim() || validSteps.length === 0) return
    setLoading(true); setError(''); setSuccess(false)
    try {
      const resp = await fetch(`${GRAPH_BASE}/graph/sop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title, fault_name: faultName,
          steps: validSteps, version, author,
          data_source: 'manual',
        }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setSuccess(true)
      setTimeout(onSaved, 1200)
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <div className="form-grid">
        <div className="form-field">
          <label className="form-label">关联故障名称 *</label>
          <input
            className="text-input" list="fault-opts"
            placeholder="输入或选择故障名…"
            value={faultName} onChange={(e) => setFault(e.target.value)}
          />
          <datalist id="fault-opts">{faults.map((f) => <option key={f} value={f} />)}</datalist>
        </div>

        <div className="form-field">
          <label className="form-label">SOP 标题 *</label>
          <input
            className="text-input" placeholder="如：CPU 告警标准处置流程"
            value={title} onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="form-field half">
          <label className="form-label">版本号</label>
          <input className="text-input" value={version} onChange={(e) => setVersion(e.target.value)} />
        </div>

        <div className="form-field half">
          <label className="form-label">作者</label>
          <input className="text-input" placeholder="可选" value={author} onChange={(e) => setAuthor(e.target.value)} />
        </div>
      </div>

      <div className="steps-section">
        <div className="steps-header">
          <span className="form-label">处置步骤 *</span>
          <button className="btn-sm" onClick={addStep}>+ 添加步骤</button>
        </div>
        <div className="steps-editor">
          {steps.map((step, i) => (
            <div key={i} className="step-row">
              <span className="step-num">{i + 1}</span>
              <input
                className="text-input"
                placeholder={`第 ${i + 1} 步说明…`}
                value={step}
                onChange={(e) => updateStep(i, e.target.value)}
              />
              {steps.length > 1 && (
                <button className="btn-del" onClick={() => removeStep(i)}>✕</button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="form-actions">
        <button className="btn-primary" onClick={submit}
          disabled={loading || !title.trim() || !faultName.trim() || steps.filter(s => s.trim()).length === 0}>
          {loading ? '保存中…' : initial ? '更新 SOP' : '创建 SOP'}
        </button>
        <button className="btn-outline" onClick={onSaved}>取消</button>
      </div>

      {success && <div className="msg-ok">✅ SOP 已保存，正在返回列表…</div>}
      {error   && <div className="msg-error">❌ {error}</div>}
    </div>
  )
}
