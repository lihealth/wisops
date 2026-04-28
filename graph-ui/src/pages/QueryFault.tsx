import { useState, useEffect } from 'react'
import { querySolutions, getFaults, Solution } from '../api'
import { Link } from 'react-router-dom'

export default function QueryFault() {
  const [faultName, setFaultName] = useState('')
  const [faultList, setFaultList] = useState<string[]>([])
  const [solutions, setSolutions] = useState<Solution[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [queried, setQueried] = useState(false)

  useEffect(() => {
    getFaults().then((r) => setFaultList(r.faults)).catch(() => {})
  }, [])

  async function handleQuery(e: React.FormEvent) {
    e.preventDefault()
    if (!faultName.trim()) return

    setLoading(true)
    setError(null)
    setSolutions(null)
    setQueried(false)
    try {
      const res = await querySolutions(faultName.trim())
      setSolutions(res.solutions)
      setQueried(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div className="card-title">
        <span>🔍</span> 按故障查询方案
      </div>

      <form onSubmit={handleQuery}>
        <div className="query-bar">
          <input
            className="form-input"
            list="fault-list"
            placeholder="输入故障名称，如：CPU告警"
            value={faultName}
            onChange={(e) => setFaultName(e.target.value)}
          />
          <datalist id="fault-list">
            {faultList.map((f) => (
              <option key={f} value={f} />
            ))}
          </datalist>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !faultName.trim()}
          >
            {loading ? '查询中...' : '查询'}
          </button>
        </div>
      </form>

      {error && (
        <div className="alert alert-error">{`❌ ${error}`}</div>
      )}

      {queried && solutions !== null && (
        solutions.length === 0 ? (
          <div className="empty-state">
            <p>该故障暂无方案记录</p>
            <p style={{ marginTop: 8 }}>
              <Link to="/add">前往录入页</Link> 添加一条方案
            </p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 8 }}>
              共找到 <strong>{solutions.length}</strong> 条方案
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '28%' }}>方案名称</th>
                    <th>方案描述</th>
                  </tr>
                </thead>
                <tbody>
                  {solutions.map((s) => (
                    <tr key={s.id}>
                      <td><strong>{s.name}</strong></td>
                      <td style={{ color: s.description ? '#374151' : '#9ca3af' }}>
                        {s.description || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      )}

      {!queried && !error && (
        <div className="empty-state">
          <p>输入故障名称后点击查询</p>
          {faultList.length > 0 && (
            <p style={{ marginTop: 8 }}>
              已有 <strong>{faultList.length}</strong> 类故障数据，输入框支持下拉提示
            </p>
          )}
        </div>
      )}
    </div>
  )
}
