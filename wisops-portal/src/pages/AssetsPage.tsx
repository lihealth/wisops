import { useState, useEffect } from 'react'
import './AssetsPage.css'

const GRAPH_BASE = '/graph-api'

interface AssetRow {
  asset_id: string
  name: string
  asset_type: string
  ip: string
  env: string
  data_source: string
}

interface AlertRow {
  alert_id: string
  content: string
  level: string
  source: string
  occurred_at: number
}

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const

function formatTime(ms: number): string {
  if (!ms || ms <= 0) return '—'
  try {
    return new Date(ms).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return '—'
  }
}

export default function AssetsPage() {
  const [items, setItems] = useState<AssetRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AssetRow | null>(null)
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertsError, setAlertsError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const t = window.setTimeout(() => setQ(qInput.trim()), 300)
    return () => window.clearTimeout(t)
  }, [qInput])

  useEffect(() => {
    setPage(1)
  }, [q, pageSize])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (q) params.set('q', q)
    fetch(`${GRAPH_BASE}/assets?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (cancelled) return
        setItems(d.assets ?? [])
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
  }, [page, pageSize, q, refreshKey])

  useEffect(() => {
    if (!selected?.asset_id) {
      setAlerts([])
      return
    }
    let cancelled = false
    setAlertsLoading(true)
    setAlertsError('')
    const params = new URLSearchParams({
      asset_id: selected.asset_id,
      page: '1',
      page_size: '30',
    })
    fetch(`${GRAPH_BASE}/alerts?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (!cancelled) setAlerts(d.alerts ?? [])
      })
      .catch((e) => {
        if (!cancelled) setAlertsError(e instanceof Error ? e.message : '告警加载失败')
      })
      .finally(() => {
        if (!cancelled) setAlertsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected?.asset_id])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="assets-page">
      <div className="assets-header">
        <span className="assets-title">资产管理</span>
        <button type="button" className="btn-outline" onClick={() => setRefreshKey((k) => k + 1)}>
          刷新
        </button>
      </div>
      <div className="assets-body">
        <div className="assets-main">
          <p className="assets-hint">
            数据来自图谱 <strong>Asset</strong> 顶点；点击行可在右侧查看属性与关联的 <strong>HAS_ALERT</strong> 告警（最近 30 条）。
            筛选框将调用 <code className="mono">GET /assets?q=</code>（子串匹配 asset_id / 名称 / IP）。批量写入请使用{' '}
            <code className="mono">POST /assets/sync</code> 或导入脚本。
          </p>
          <div className="assets-toolbar">
            <input
              className="text-input"
              placeholder="按 asset_id / 名称 / IP 筛选（子串）…"
              value={qInput}
              onChange={(e) => setQInput(e.target.value)}
            />
            <label className="assets-page-size-label">
              每页
              <select
                className="assets-page-size-select"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {error && <div className="msg-error">{error}</div>}
          {loading && <div className="loading">加载中…</div>}
          {!loading && !error && (
            <>
              <div className="assets-table-wrap">
                <table className="assets-table">
                  <thead>
                    <tr>
                      <th>asset_id</th>
                      <th>名称</th>
                      <th>类型</th>
                      <th>IP</th>
                      <th>环境</th>
                      <th>来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="empty" style={{ border: 'none' }}>
                          暂无资产数据
                        </td>
                      </tr>
                    ) : (
                      items.map((row) => (
                        <tr
                          key={row.asset_id}
                          className={selected?.asset_id === row.asset_id ? 'selected' : ''}
                          onClick={() => setSelected(row)}
                        >
                          <td className="mono">{row.asset_id}</td>
                          <td>{row.name || '—'}</td>
                          <td>{row.asset_type || '—'}</td>
                          <td className="mono">{row.ip || '—'}</td>
                          <td>{row.env || '—'}</td>
                          <td className="cell-muted">{row.data_source || '—'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div className="assets-pagination">
                <button type="button" className="btn-page" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  上一页
                </button>
                <span className="page-info">
                  第 {page} / {totalPages} 页 · 共 {total} 条
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
            </>
          )}
        </div>
        <aside className="assets-side">
          <h2 className="assets-side-title">资产详情</h2>
          {!selected ? (
            <p className="assets-detail-empty">在左侧列表中点击一行，即可查看该资产的属性与近期告警。</p>
          ) : (
            <>
              <div className="detail-grid">
                <div className="detail-row">
                  <span className="detail-k">asset_id</span>
                  <span className="detail-v mono">{selected.asset_id}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-k">名称</span>
                  <span className="detail-v">{selected.name || '—'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-k">类型</span>
                  <span className="detail-v">{selected.asset_type || '—'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-k">IP</span>
                  <span className="detail-v mono">{selected.ip || '—'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-k">环境</span>
                  <span className="detail-v">{selected.env || '—'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-k">data_source</span>
                  <span className="detail-v">{selected.data_source || '—'}</span>
                </div>
              </div>
              <div className="alerts-block">
                <div className="alerts-title">关联告警（HAS_ALERT，最多 30 条）</div>
                {alertsLoading && <div className="loading" style={{ padding: '1rem' }}>加载告警…</div>}
                {alertsError && <div className="msg-error">{alertsError}</div>}
                {!alertsLoading && !alertsError && alerts.length === 0 && (
                  <p className="assets-detail-empty">暂无关联告警。</p>
                )}
                {!alertsLoading &&
                  alerts.map((a) => (
                    <div key={a.alert_id} className="alert-item">
                      <div className="alert-meta">
                        <span className="mono">{a.alert_id}</span>
                        {' · '}
                        {a.level}
                        {' · '}
                        {a.source}
                        {' · '}
                        {formatTime(a.occurred_at)}
                      </div>
                      <div className="alert-content">{a.content}</div>
                    </div>
                  ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
