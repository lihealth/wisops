import { useState } from 'react'
import { addRelation } from '../api'

type Status = { type: 'success' | 'info' | 'error'; msg: string } | null

export default function AddFault() {
  const [faultName, setFaultName] = useState('')
  const [solutionName, setSolutionName] = useState('')
  const [solutionDesc, setSolutionDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<Status>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!faultName.trim() || !solutionName.trim()) return

    setLoading(true)
    setStatus(null)
    try {
      const res = await addRelation(faultName.trim(), solutionName.trim(), solutionDesc.trim())
      if (res.edge_status === 'created') {
        setStatus({ type: 'success', msg: '✅ 录入成功！故障–方案关系已写入图谱。' })
        setFaultName('')
        setSolutionName('')
        setSolutionDesc('')
      } else {
        setStatus({ type: 'info', msg: 'ℹ️ 该故障–方案关系已存在，无需重复录入。' })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误'
      setStatus({ type: 'error', msg: `❌ 录入失败：${msg}` })
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setFaultName('')
    setSolutionName('')
    setSolutionDesc('')
    setStatus(null)
  }

  return (
    <div className="card">
      <div className="card-title">
        <span>📝</span> 故障–方案录入
      </div>

      {status && (
        <div className={`alert alert-${status.type}`} style={{ marginBottom: 20 }}>
          {status.msg}
        </div>
      )}

      <form className="form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">
            故障名称 <span className="required">*</span>
          </label>
          <input
            className="form-input"
            placeholder="例：CPU告警"
            value={faultName}
            onChange={(e) => setFaultName(e.target.value)}
            maxLength={200}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            方案名称 <span className="required">*</span>
          </label>
          <input
            className="form-input"
            placeholder="例：检查高负载进程并限流"
            value={solutionName}
            onChange={(e) => setSolutionName(e.target.value)}
            maxLength={200}
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">方案描述</label>
          <textarea
            className="form-textarea"
            placeholder="详细描述解决步骤（选填）"
            value={solutionDesc}
            onChange={(e) => setSolutionDesc(e.target.value)}
            maxLength={2000}
          />
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !faultName.trim() || !solutionName.trim()}
          >
            {loading ? '提交中...' : '录入图谱'}
          </button>
          <button type="button" className="btn btn-outline" onClick={handleReset}>
            清空
          </button>
        </div>
      </form>
    </div>
  )
}
