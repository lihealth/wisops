import { useState, useRef, useEffect, useCallback } from 'react'
import './ChatPage.css'

interface GraphContext {
  /** 兼容旧版详情面板渲染 */
  fault_name?: string
  summary_text: string
  solutions?: Array<{ name: string; description: string; data_source: string }>
  sops?: Array<{ title: string; version: string }>
  /** /chat/context 返回的 Dify inputs 对象 */
  dify_inputs?: Record<string, string>
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
  graphCtx?: GraphContext | null
  recommendations?: Array<{ fault_name: string; similarity: number; solutions: Array<{ name: string }> }>
}

const DIFY_API_KEY_ENV = import.meta.env.VITE_DIFY_API_KEY ?? ''
const LS_KEY           = 'wisops_dify_api_key'
const DIFY_BASE        = '/dify-api'
const GRAPH_BASE       = '/graph-api'

type ChatMode = 'rag' | 'graph' | 'auto'

function uid() { return Math.random().toString(36).slice(2) }
function loadKey() { return DIFY_API_KEY_ENV || localStorage.getItem(LS_KEY) || '' }

/**
 * 统一调用 /chat/context 获取图谱上下文，返回：
 *  - ctx       : 可渲染到助手气泡的 GraphContext
 *  - recs      : 推荐列表（供参考面板渲染）
 *  - difyInputs: 直接注入 Dify inputs 的 dict
 */
async function fetchGraphContext(query: string): Promise<{
  ctx: GraphContext | null
  recs: Message['recommendations']
  difyInputs: Record<string, string>
}> {
  try {
    const res = await fetch(`${GRAPH_BASE}/chat/context?q=${encodeURIComponent(query)}&top_k=5`)
    if (!res.ok) return { ctx: null, recs: undefined, difyInputs: {} }
    const data = await res.json()

    const recs: Message['recommendations'] = data.recommendations?.length > 0
      ? data.recommendations
      : undefined

    const summaryText: string = data.summary_text ?? ''
    const ctx: GraphContext | null = summaryText
      ? { summary_text: summaryText, dify_inputs: data.inputs }
      : null

    return { ctx, recs, difyInputs: data.inputs ?? {} }
  } catch {
    return { ctx: null, recs: undefined, difyInputs: {} }
  }
}

function buildGraphOnlyAssistantText(
  query: string,
  ctx: GraphContext | null,
  recs: Message['recommendations'],
): string {
  const lines: string[] = []
  lines.push('当前未配置 Dify API Key，以下为图谱检索结果（无知识库流式回答）。可在右上角 🔑 填入 Key 后使用完整 RAG。')
  lines.push('')
  if (ctx?.summary_text) {
    lines.push(ctx.summary_text)
  }
  if (recs?.length) {
    lines.push('')
    lines.push('—— 相似故障参考 ——')
    recs.forEach((r, i) => {
      const pct = Number.isFinite(r.similarity) ? `${Math.round(r.similarity * 100)}%` : ''
      lines.push(`${i + 1}. ${r.fault_name}${pct ? `（相似度 ${pct}）` : ''}`)
      if (r.solutions?.length) {
        lines.push(`   方案：${r.solutions.map((s) => s.name).join(' · ')}`)
      }
    })
  }
  if (!ctx?.summary_text && !recs?.length) {
    lines.push(`未在图谱中命中与「${query.slice(0, 80)}」相关的摘要或相似故障，可换关键词重试。`)
  }
  return lines.join('\n')
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: uid(), role: 'assistant', content: '你好！我是 WisOps V2.0 智能助手。可选「图谱融合 / 自动」仅使用图谱相似推荐与摘要（无需 Dify）；配置右上角 🔑 后可使用完整知识库 RAG。请描述你的运维问题。' }
  ])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [convId, setConvId]     = useState<string | undefined>()
  const [apiKey, setApiKey]     = useState(loadKey)
  const [showKey, setShowKey]   = useState(false)
  const [mode, setMode]         = useState<ChatMode>('auto')
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef  = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    if (!apiKey && mode === 'rag') {
      setShowKey(true)
      return
    }

    setInput('')
    const userMsg: Message = { id: uid(), role: 'user', content: text }
    const asstId = uid()
    const asstMsg: Message = { id: asstId, role: 'assistant', content: '', loading: true }

    setMessages((prev) => [...prev, userMsg, asstMsg])
    setLoading(true)

    // Graph-RAG 上下文预取（auto / graph 模式）
    let graphCtx: GraphContext | null = null
    let recs: Message['recommendations'] = undefined
    let difyInputs: Record<string, string> = {}
    if (mode === 'auto' || mode === 'graph') {
      const result = await fetchGraphContext(text)
      graphCtx = result.ctx
      recs = result.recs
      difyInputs = result.difyInputs
      if (graphCtx || recs) {
        setMessages((prev) => prev.map((m) =>
          m.id === asstId ? { ...m, graphCtx, recommendations: recs } : m
        ))
      }
    }

    // 无 Dify Key：仅图谱模式可用，直接展示检索文案与卡片，不调知识库
    if (!apiKey && (mode === 'auto' || mode === 'graph')) {
      const body = buildGraphOnlyAssistantText(text, graphCtx, recs)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstId
            ? { ...m, content: body, loading: false, graphCtx, recommendations: recs }
            : m
        )
      )
      setLoading(false)
      return
    }

    abortRef.current = new AbortController()

    try {
      // 图谱上下文通过 inputs.graph_context 注入 Dify（结构化），不再拼入 query
      const res = await fetch(`${DIFY_BASE}/v1/chat-messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          inputs: difyInputs,          // { graph_context: "...", query: "..." }
          query: text,                 // 用户原始提问，不再附加上下文字符串
          response_mode: 'streaming',
          conversation_id: convId ?? '',
          user: 'wisops-portal',
        }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ message: '请求失败' }))
        throw new Error(err.message ?? `HTTP ${res.status}`)
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let answer = ''
      let cid = convId

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const json = line.slice(6).trim()
          if (json === '[DONE]') continue
          try {
            const evt = JSON.parse(json)
            if (evt.event === 'message' && evt.answer) {
              answer += evt.answer
              setMessages((prev) =>
                prev.map((m) => m.id === asstId ? { ...m, content: answer, loading: true } : m)
              )
            }
            if (evt.event === 'message_end') {
              cid = evt.conversation_id
            }
          } catch { /* skip malformed */ }
        }
      }

      if (cid) setConvId(cid)
      setMessages((prev) =>
        prev.map((m) => m.id === asstId
          ? { ...m, content: answer || '（无回复）', loading: false, graphCtx, recommendations: recs }
          : m
        )
      )
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return
      const msg = e instanceof Error ? e.message : '未知错误'
      setMessages((prev) =>
        prev.map((m) => m.id === asstId
          ? { ...m, content: `❌ 请求失败：${msg}`, loading: false, graphCtx: null }
          : m
        )
      )
    } finally {
      setLoading(false)
    }
  }, [input, loading, apiKey, convId, mode])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const clearChat = () => {
    setMessages([{ id: uid(), role: 'assistant', content: '会话已重置，请输入新问题。' }])
    setConvId(undefined)
    abortRef.current?.abort()
  }

  const MODE_LABELS: Record<ChatMode, string> = {
    auto:  '🔀 自动',
    rag:   '📚 纯 RAG',
    graph: '🕸️ 图谱融合',
  }

  return (
    <div className="chat-page">

      {/* Header */}
      <div className="chat-header">
        <div>
          <span className="chat-title">AI 智能问答</span>
          {convId && <span className="conv-id">会话 {convId.slice(0,8)}…</span>}
        </div>
        <div className="chat-actions">
          <div className="mode-switch">
            {(Object.keys(MODE_LABELS) as ChatMode[]).map((m) => (
              <button
                key={m}
                className={`mode-btn ${mode === m ? 'active' : ''}`}
                onClick={() => setMode(m)}
                title={m === 'auto' ? '自动检测故障关键词，融合图谱上下文' : m === 'rag' ? '仅使用知识库检索' : '强制融合图谱上下文'}
              >
                {MODE_LABELS[m]}
              </button>
            ))}
          </div>
          <button className="icon-btn" title="设置 API Key" onClick={() => setShowKey((v) => !v)}>🔑</button>
          <button className="icon-btn" title="清空会话" onClick={clearChat}>🗑️</button>
        </div>
      </div>

      {/* API Key 配置条 */}
      {showKey && (
        <div className="apikey-bar">
          <span>Dify API Key：</span>
          <input
            type="password"
            placeholder="app-xxxxxxxxxxxxxxxx"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="apikey-input"
          />
          <button className="btn-sm" onClick={() => {
            localStorage.setItem(LS_KEY, apiKey)
            setShowKey(false)
          }}>确认</button>
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((m) => (
          <div key={m.id} className={`msg msg-${m.role}`}>
            <div className="msg-avatar">{m.role === 'user' ? '👤' : '🤖'}</div>
            <div className="msg-wrap">
              {/* 图谱摘要卡（仅 assistant） */}
              {m.role === 'assistant' && m.graphCtx && (
                <GraphContextCard ctx={m.graphCtx} />
              )}
              {/* 相似推荐卡 */}
              {m.role === 'assistant' && m.recommendations && m.recommendations.length > 0 && (
                <RecommendCard recs={m.recommendations} />
              )}
              <div className="msg-bubble">
                {m.content || (m.loading ? '' : '…')}
                {m.loading && <span className="cursor-blink">▌</span>}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-wrap">
        <textarea
          className="chat-input"
          placeholder="输入运维问题，按 Enter 发送（Shift+Enter 换行）"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          disabled={loading}
        />
        <button
          className="send-btn"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          {loading ? '⏳' : '发送'}
        </button>
      </div>
    </div>
  )
}

function GraphContextCard({ ctx }: { ctx: GraphContext }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="graph-ctx-card">
      <div className="ctx-header" onClick={() => setOpen((v) => !v)}>
        <span className="ctx-badge">🕸️ 图谱知识</span>
        <span className="ctx-fault">{ctx.fault_name}</span>
        <span className="ctx-count">{ctx.solutions?.length ?? 0} 条方案</span>
        <span className="ctx-toggle">{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="ctx-body">
          {(ctx.solutions ?? []).slice(0, 3).map((s, i) => (
            <div key={i} className="ctx-sol">
              <span className="ctx-sol-num">{i + 1}</span>
              <div>
                <div className="ctx-sol-name">{s.name}</div>
                {s.description && <div className="ctx-sol-desc">{s.description.slice(0, 120)}{s.description.length > 120 ? '…' : ''}</div>}
              </div>
              <span className="ctx-src">{s.data_source}</span>
            </div>
          ))}
          {(ctx.sops?.length ?? 0) > 0 && (
            <div className="ctx-sop">📋 关联 SOP：{ctx.sops![0].title}（v{ctx.sops![0].version}）</div>
          )}
        </div>
      )}
    </div>
  )
}

function RecommendCard({ recs }: { recs: NonNullable<Message['recommendations']> }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rec-card">
      <div className="ctx-header" onClick={() => setOpen((v) => !v)}>
        <span className="ctx-badge rec-badge">💡 相似故障推荐</span>
        <span className="ctx-count">{recs.length} 条</span>
        <span className="ctx-toggle">{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="ctx-body">
          {recs.map((r, i) => (
            <div key={i} className="rec-item">
              <span className="rec-score">{Math.round(r.similarity * 100)}%</span>
              <div>
                <div className="ctx-sol-name">{r.fault_name}</div>
                {r.solutions.length > 0 && (
                  <div className="ctx-sol-desc">{r.solutions.map(s => s.name).join(' · ')}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
