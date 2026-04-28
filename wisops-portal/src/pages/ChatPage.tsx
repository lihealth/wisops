import { useState, useRef, useEffect, useCallback } from 'react'
import './ChatPage.css'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

const DIFY_API_KEY = import.meta.env.VITE_DIFY_API_KEY ?? ''
const DIFY_BASE    = '/dify-api'

function uid() { return Math.random().toString(36).slice(2) }

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: uid(), role: 'assistant', content: '你好！我是 WisOps 智能助手，可以帮你查询运维知识库。请描述你遇到的问题。' }
  ])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [convId, setConvId]     = useState<string | undefined>()
  const [apiKey, setApiKey]     = useState(DIFY_API_KEY)
  const [showKey, setShowKey]   = useState(!DIFY_API_KEY)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef  = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return
    if (!apiKey) { setShowKey(true); return }

    setInput('')
    const userMsg: Message = { id: uid(), role: 'user', content: text }
    const asstId = uid()
    const asstMsg: Message = { id: asstId, role: 'assistant', content: '', loading: true }

    setMessages((prev) => [...prev, userMsg, asstMsg])
    setLoading(true)

    abortRef.current = new AbortController()

    try {
      const res = await fetch(`${DIFY_BASE}/v1/chat-messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          inputs: {},
          query: text,
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
        prev.map((m) => m.id === asstId ? { ...m, content: answer || '（无回复）', loading: false } : m)
      )
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return
      const msg = e instanceof Error ? e.message : '未知错误'
      setMessages((prev) =>
        prev.map((m) => m.id === asstId
          ? { ...m, content: `❌ 请求失败：${msg}`, loading: false }
          : m
        )
      )
    } finally {
      setLoading(false)
    }
  }, [input, loading, apiKey, convId])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const clearChat = () => {
    setMessages([{ id: uid(), role: 'assistant', content: '会话已重置，请输入新问题。' }])
    setConvId(undefined)
    abortRef.current?.abort()
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
          <button className="btn-sm" onClick={() => setShowKey(false)}>确认</button>
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((m) => (
          <div key={m.id} className={`msg msg-${m.role}`}>
            <div className="msg-avatar">{m.role === 'user' ? '👤' : '🤖'}</div>
            <div className="msg-bubble">
              {m.content || (m.loading ? '' : '…')}
              {m.loading && <span className="cursor-blink">▌</span>}
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
