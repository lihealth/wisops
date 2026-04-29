import { useState, useEffect } from 'react'
import './DashboardPage.css'

const GRAPH_BASE = '/graph-api'

interface Stats {
  node_counts: Record<string, number>
  coverage_rate: number
  reuse_rate: number
  extract_rate: number
  source_distribution: Record<string, number>
  extract_queue: { total: number; pending: number; approved: number; rejected: number }
}

interface Growth {
  window: string
  new_nodes: Record<string, number>
}

const SOURCE_LABEL: Record<string, string> = {
  manual:              '手工录入',
  extracted_approved:  '抽取审核',
  open_gaia:           'GAIA 数据集（open_gaia）',
  gaia:                'GAIA 导入',
  gen_template:        '模板生成',
  logHub:              'LogHub',
  stackoverflow:       'StackOverflow',
  internal_ticket:     '内部工单',
  unset:               '未设置 data_source',
  unknown:             '未知',
}

export default function DashboardPage() {
  const [stats, setStats]     = useState<Stats | null>(null)
  const [growth, setGrowth]   = useState<Growth | null>(null)
  const [window_, setWindow]  = useState<'week' | 'month'>('week')
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const fetchAll = async () => {
    setLoading(true); setError('')
    try {
      const [sRes, gRes] = await Promise.all([
        fetch(`${GRAPH_BASE}/ops/stats`),
        fetch(`${GRAPH_BASE}/ops/stats/growth?window=${window_}`),
      ])
      if (!sRes.ok || !gRes.ok) throw new Error('接口请求失败')
      setStats(await sRes.json())
      setGrowth(await gRes.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [window_])

  if (loading) return <div className="db-loading">加载中…</div>
  if (error)   return <div className="db-error">❌ {error} <button onClick={fetchAll}>重试</button></div>
  if (!stats)  return null

  const totalNodes = Object.values(stats.node_counts).reduce((a, b) => a + b, 0)

  return (
    <div className="dashboard">
      <div className="db-header">
        <span className="db-title">运营看板</span>
        <button className="btn-outline" onClick={fetchAll}>刷新</button>
      </div>

      {/* 核心指标卡 */}
      <div className="metric-grid">
        <MetricCard
          label="图谱节点总量"
          value={totalNodes.toLocaleString()}
          sub="所有实体类型合计"
          color="blue"
          icon="🕸️"
        />
        <MetricCard
          label="知识覆盖率"
          value={`${stats.coverage_rate}%`}
          sub="有方案的故障占比"
          color={stats.coverage_rate >= 80 ? 'green' : stats.coverage_rate >= 50 ? 'yellow' : 'red'}
          icon="📊"
        />
        <MetricCard
          label="方案复用率"
          value={`${stats.reuse_rate}%`}
          sub="工单命中已有方案"
          color={stats.reuse_rate >= 60 ? 'green' : 'yellow'}
          icon="♻️"
        />
        <MetricCard
          label="抽取转化率"
          value={`${stats.extract_rate}%`}
          sub="审核通过 / 总提交"
          color={stats.extract_rate >= 50 ? 'green' : 'yellow'}
          icon="🤖"
        />
      </div>

      <div className="db-row">
        {/* 实体分布 */}
        <div className="db-card">
          <div className="card-title">节点类型分布</div>
          <div className="bar-list">
            {Object.entries(stats.node_counts)
              .sort((a, b) => b[1] - a[1])
              .map(([label, count]) => (
                <div key={label} className="bar-row">
                  <span className="bar-label">{label}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: totalNodes > 0 ? `${count / totalNodes * 100}%` : '0%' }}
                    />
                  </div>
                  <span className="bar-count">{count.toLocaleString()}</span>
                </div>
              ))}
          </div>
        </div>

        {/* 数据来源分布 */}
        <div className="db-card">
          <div className="card-title">数据来源分布（Fault）</div>
          {Object.keys(stats.source_distribution).length === 0 ? (
            <div className="empty-hint">暂无数据</div>
          ) : (
            <div className="source-list">
              {Object.entries(stats.source_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([src, count]) => {
                  const total = Object.values(stats.source_distribution).reduce((a, b) => a + b, 0)
                  const pct   = total > 0 ? Math.round(count / total * 100) : 0
                  return (
                    <div key={src} className="source-row">
                      <span className="source-dot" />
                      <span className="source-name">{SOURCE_LABEL[src] ?? src}</span>
                      <div className="bar-track">
                        <div className="bar-fill src-fill" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="source-count">{count} ({pct}%)</span>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </div>

      <div className="db-row">
        {/* 增长趋势 */}
        <div className="db-card">
          <div className="card-header">
            <div className="card-title">知识增长</div>
            <div className="window-switch">
              <button className={window_ === 'week' ? 'win-btn active' : 'win-btn'} onClick={() => setWindow('week')}>本周</button>
              <button className={window_ === 'month' ? 'win-btn active' : 'win-btn'} onClick={() => setWindow('month')}>本月</button>
            </div>
          </div>
          {growth && (
            <div className="growth-grid">
              {Object.entries(growth.new_nodes).map(([label, count]) => (
                <div key={label} className="growth-item">
                  <div className="growth-count">{count > 0 ? `+${count}` : count}</div>
                  <div className="growth-label">{label}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 抽取队列状态 */}
        <div className="db-card">
          <div className="card-title">抽取队列状态</div>
          <div className="queue-stats">
            <QueueStat label="总提交" value={stats.extract_queue.total} color="#94a3b8" />
            <QueueStat label="待审核" value={stats.extract_queue.pending}  color="#60a5fa" />
            <QueueStat label="已通过" value={stats.extract_queue.approved} color="#4ade80" />
            <QueueStat label="已拒绝" value={stats.extract_queue.rejected} color="#f87171" />
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, sub, color, icon }: {
  label: string; value: string; sub: string; color: string; icon: string
}) {
  return (
    <div className={`metric-card metric-${color}`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-body">
        <div className="metric-value">{value}</div>
        <div className="metric-label">{label}</div>
        <div className="metric-sub">{sub}</div>
      </div>
    </div>
  )
}

function QueueStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="qs-item">
      <div className="qs-value" style={{ color }}>{value}</div>
      <div className="qs-label">{label}</div>
    </div>
  )
}
