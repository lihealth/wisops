import { useState, useEffect, useCallback } from 'react'
import './IncidentPage.css'

const GRAPH_BASE = '/graph-api'

interface IncidentRow {
  incident_id: string
  title: string
  status: string
  mttr_minutes: number
  created_at: number
  data_source: string
}

interface IncidentDetail extends IncidentRow {
  faults: string[]
  solutions: Array<{ name: string; description: string }>
  assets: Array<{ asset_id: string; name: string; asset_type: string; ip: string }>
}

function formatTime(ms: number) {
  if (!ms || ms <= 0) return '—'
  try { return new Date(ms).toLocaleString('zh-CN', { hour12: false }) } catch { return '—' }
}

function uid() { return `INC-${Date.now()}-${Math.random().toString(36).slice(2, 7).toUpperCase()}` }

export default function IncidentPage() {
  const [tab, setTab] = useState<'list' | 'add'>('list')
  const [refreshKey, setRefreshKey] = useState(0)
  const [detailId, setDetailId] = useState<string | null>(null)

  const onCreated = () => { setRefreshKey(k => k + 1); setTab('list') }

  return (
    <div className="incident-page">
      <div className="incident-header">
        <span className="incident-title">工单沉淀</span>
        <div className="incident-tabs">
          <button className={tab === 'list' ? 'itab active' : 'itab'} onClick={() => { setTab('list'); setDetailId(null) }}>工单列表</button>
          <button className={tab === 'add'  ? 'itab active' : 'itab'} onClick={() => setTab('add')}>录入工单</button>
        </div>
      </div>
      <div className="incident-body">
        {tab === 'list' && !detailId && (
          <IncidentList key={refreshKey} onSelect={setDetailId} />
        )}
        {tab === 'list' && detailId && (
          <IncidentDetailPanel incidentId={detailId} onBack={() => setDetailId(null)} />
        )}
        {tab === 'add' && <IncidentForm onCreated={onCreated} />}
      </div>
    </div>
  )
}

/* ────────────────── 工单列表 ────────────────── */
function IncidentList({ onSelect }: { onSelect: (id: string) => void }) {
  const [items, setItems]   = useState<IncidentRow[]>([])
  const [page, setPage]     = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState('')

  const fetchPage = useCallback(async (p: number) => {
    setLoading(true); setError('')
    try {
      const r = await fetch(`${GRAPH_BASE}/incidents?page=${p}&page_size=20`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const d = await r.json()
      setItems(d.incidents ?? [])
      setPage(p)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchPage(1) }, [fetchPage])

  return (
    <div className="i-panel">
      <div className="i-toolbar">
        <span className="i-section-title">工单列表</span>
        <button className="i-btn-outline" onClick={() => fetchPage(page)}>刷新</button>
      </div>
      {error && <div className="i-msg-error">❌ {error}</div>}
      {loading ? <div className="i-loading">加载中…</div> : items.length === 0 ? (
        <div className="i-empty">暂无工单，请先录入</div>
      ) : (
        <>
          <div className="i-table-wrap">
            <table className="i-table">
              <thead>
                <tr><th>工单 ID</th><th>标题</th><th>MTTR（分钟）</th><th>数据源</th><th>创建时间</th><th></th></tr>
              </thead>
              <tbody>
                {items.map(it => (
                  <tr key={it.incident_id} onClick={() => onSelect(it.incident_id)} className="i-row-link">
                    <td className="mono">{it.incident_id}</td>
                    <td>{it.title}</td>
                    <td>{it.mttr_minutes > 0 ? it.mttr_minutes : '—'}</td>
                    <td><span className="i-src-tag">{it.data_source}</span></td>
                    <td>{formatTime(it.created_at)}</td>
                    <td><button className="i-btn-detail" onClick={e => { e.stopPropagation(); onSelect(it.incident_id) }}>详情 →</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="i-pager">
            <button className="i-btn-outline" disabled={page <= 1} onClick={() => fetchPage(page - 1)}>上一页</button>
            <span className="i-page-num">第 {page} 页</span>
            <button className="i-btn-outline" disabled={items.length < 20} onClick={() => fetchPage(page + 1)}>下一页</button>
          </div>
        </>
      )}
    </div>
  )
}

/* ────────────────── 工单详情 ────────────────── */
function IncidentDetailPanel({ incidentId, onBack }: { incidentId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<IncidentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true); setError('')
    fetch(`${GRAPH_BASE}/incidents/${encodeURIComponent(incidentId)}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => setDetail(d))
      .catch(e => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false))
  }, [incidentId])

  return (
    <div className="i-panel">
      <div className="i-toolbar">
        <button className="i-btn-back" onClick={onBack}>← 返回列表</button>
        <span className="i-section-title">工单详情</span>
      </div>
      {loading ? <div className="i-loading">加载中…</div>
        : error ? <div className="i-msg-error">❌ {error}</div>
        : detail && (
          <div className="i-detail-wrap">
            <div className="i-detail-card">
              <div className="i-detail-row"><span className="i-detail-label">工单 ID</span><span className="mono">{detail.incident_id}</span></div>
              <div className="i-detail-row"><span className="i-detail-label">标题</span><span>{detail.title}</span></div>
              <div className="i-detail-row"><span className="i-detail-label">MTTR</span><span>{detail.mttr_minutes > 0 ? `${detail.mttr_minutes} 分钟` : '—'}</span></div>
              <div className="i-detail-row"><span className="i-detail-label">数据源</span><span className="i-src-tag">{detail.data_source}</span></div>
              <div className="i-detail-row"><span className="i-detail-label">创建时间</span><span>{formatTime(detail.created_at)}</span></div>
            </div>

            <div className="i-assoc-section">
              <div className="i-assoc-title">关联故障（CAUSED_BY）</div>
              {detail.faults?.length > 0
                ? <div className="i-tag-list">{detail.faults.map(f => <span key={f} className="i-fault-tag">{f}</span>)}</div>
                : <span className="i-assoc-empty">无</span>}
            </div>

            <div className="i-assoc-section">
              <div className="i-assoc-title">使用方案（RESOLVED_BY）</div>
              {detail.solutions?.length > 0 ? (
                <div className="i-sol-list">
                  {detail.solutions.map(s => (
                    <div key={s.name} className="i-sol-card">
                      <div className="i-sol-name">{s.name}</div>
                      {s.description && <div className="i-sol-desc">{s.description.slice(0, 200)}{s.description.length > 200 ? '…' : ''}</div>}
                    </div>
                  ))}
                </div>
              ) : <span className="i-assoc-empty">无</span>}
            </div>

            <div className="i-assoc-section">
              <div className="i-assoc-title">涉及资产（INVOLVES）</div>
              {detail.assets?.length > 0 ? (
                <div className="i-asset-list">
                  {detail.assets.map(a => (
                    <div key={a.asset_id} className="i-asset-row">
                      <span className="mono">{a.asset_id}</span>
                      {a.name && <span>{a.name}</span>}
                      {a.ip && <span className="i-ip">{a.ip}</span>}
                      {a.asset_type && <span className="i-src-tag">{a.asset_type}</span>}
                    </div>
                  ))}
                </div>
              ) : <span className="i-assoc-empty">无</span>}
            </div>
          </div>
        )}
    </div>
  )
}

/* ────────────────── 录入表单 ────────────────── */
interface FormState {
  incident_id: string
  title: string
  fault_name: string
  solution_name: string
  asset_id: string
  mttr_minutes: string
  data_source: string
}

function IncidentForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState<FormState>({
    incident_id: uid(),
    title: '',
    fault_name: '',
    solution_name: '',
    asset_id: '',
    mttr_minutes: '',
    data_source: 'manual',
  })
  const [loading, setLoading] = useState(false)
  const [ok, setOk] = useState('')
  const [err, setErr] = useState('')

  // 故障/方案/资产候选列表（lazy load）
  const [faults, setFaults]   = useState<string[]>([])
  const [solutions, setSols]  = useState<string[]>([])
  const [assets, setAssets]   = useState<string[]>([])

  useEffect(() => {
    fetch(`${GRAPH_BASE}/graph/faults?page_size=200`)
      .then(r => r.json()).then(d => setFaults((d.faults ?? []).map((f: { name: string }) => f.name))).catch(() => {})
    fetch(`${GRAPH_BASE}/graph/solutions?page_size=200`)
      .then(r => r.json()).then(d => setSols((d.solutions ?? []).map((s: { name: string }) => s.name))).catch(() => {})
    fetch(`${GRAPH_BASE}/assets?page_size=200`)
      .then(r => r.json()).then(d => setAssets((d.items ?? []).map((a: { asset_id: string }) => a.asset_id))).catch(() => {})
  }, [])

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    if (!form.title.trim()) { setErr('标题必填'); return }
    setLoading(true); setOk(''); setErr('')
    try {
      const payload: Record<string, unknown> = {
        incident_id: form.incident_id.trim() || uid(),
        title: form.title.trim(),
        data_source: form.data_source,
      }
      if (form.fault_name.trim())    payload.fault_name    = form.fault_name.trim()
      if (form.solution_name.trim()) payload.solution_name = form.solution_name.trim()
      if (form.asset_id.trim())      payload.asset_id      = form.asset_id.trim()
      const mttr = parseInt(form.mttr_minutes)
      if (!isNaN(mttr) && mttr >= 0) payload.mttr_minutes = mttr

      const r = await fetch(`${GRAPH_BASE}/incidents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail ?? `HTTP ${r.status}`) }
      setOk(`✅ 工单已写入图谱，ID：${payload.incident_id}`)
      setForm(f => ({ ...f, incident_id: uid(), title: '', fault_name: '', solution_name: '', asset_id: '', mttr_minutes: '' }))
      setTimeout(onCreated, 1500)
    } catch (e) {
      setErr(e instanceof Error ? e.message : '提交失败')
    } finally { setLoading(false) }
  }

  return (
    <div className="i-panel">
      <div className="i-section-title">录入工单（手动沉淀）</div>
      <div className="i-form">
        <div className="i-form-row">
          <label className="i-label">工单 ID <span className="i-hint">（留空自动生成）</span></label>
          <input className="i-input" value={form.incident_id} onChange={set('incident_id')} placeholder="INC-xxx" />
        </div>
        <div className="i-form-row">
          <label className="i-label i-required">故障标题</label>
          <input className="i-input" value={form.title} onChange={set('title')} placeholder="简要描述本次故障，如：磁盘空间满导致服务宕机" />
        </div>
        <div className="i-form-row">
          <label className="i-label">关联故障名 <span className="i-hint">（图谱中已有的 Fault）</span></label>
          <input className="i-input" list="fault-dl" value={form.fault_name} onChange={set('fault_name')} placeholder="可为空" />
          <datalist id="fault-dl">{faults.map(f => <option key={f} value={f} />)}</datalist>
        </div>
        <div className="i-form-row">
          <label className="i-label">使用方案 <span className="i-hint">（图谱中已有的 Solution）</span></label>
          <input className="i-input" list="sol-dl" value={form.solution_name} onChange={set('solution_name')} placeholder="可为空" />
          <datalist id="sol-dl">{solutions.map(s => <option key={s} value={s} />)}</datalist>
        </div>
        <div className="i-form-row">
          <label className="i-label">涉及资产 ID <span className="i-hint">（INVOLVES 边）</span></label>
          <input className="i-input" list="asset-dl" value={form.asset_id} onChange={set('asset_id')} placeholder="可为空" />
          <datalist id="asset-dl">{assets.map(a => <option key={a} value={a} />)}</datalist>
        </div>
        <div className="i-form-row">
          <label className="i-label">MTTR（分钟）</label>
          <input className="i-input i-input-sm" type="number" min={0} value={form.mttr_minutes} onChange={set('mttr_minutes')} placeholder="0" />
        </div>
        <div className="i-form-row">
          <label className="i-label">数据源</label>
          <select className="i-select" value={form.data_source} onChange={set('data_source')}>
            <option value="manual">manual</option>
            <option value="internal_ticket">internal_ticket</option>
            <option value="open_gaia">open_gaia</option>
          </select>
        </div>
        <div className="i-form-actions">
          <button className="i-btn-primary" onClick={submit} disabled={loading || !form.title.trim()}>
            {loading ? '提交中…' : '写入图谱'}
          </button>
        </div>
        {ok  && <div className="i-msg-ok">{ok}</div>}
        {err && <div className="i-msg-error">❌ {err}</div>}
      </div>
      <div className="i-tip-box">
        <div className="i-tip-title">说明</div>
        <ul className="i-tip-list">
          <li>工单写入后会在图谱中建立 <strong>Incident</strong> 节点，并可选关联 Fault（CAUSED_BY）、Solution（RESOLVED_BY）、Asset（INVOLVES）边</li>
          <li>故障名、方案名支持自动补全（从图谱已有节点中筛选）；也可直接填写新名称</li>
          <li>MTTR 会纳入运营看板「平均处理时长」统计</li>
          <li>已有相同 ID 的工单会被跳过（幂等写入），可安全重复提交</li>
        </ul>
      </div>
    </div>
  )
}
