import { useNavigate } from 'react-router-dom'
import './HomePage.css'

const CARDS = [
  {
    icon: '🤖',
    color: 'blue',
    title: 'AI 智能问答',
    desc: '基于 RAG 的知识库问答，输入运维问题，AI 实时检索知识文档给出答案，支持流式输出。',
    tags: ['RAG 检索', 'AI 对话', '流式输出'],
    to: '/chat',
  },
  {
    icon: '🕸️',
    color: 'green',
    title: '故障图谱管理',
    desc: '基于 HugeGraph 的故障-方案知识图谱，录入故障关联关系，精准查询历史处置经验。',
    tags: ['知识图谱', '故障录入', '方案查询'],
    to: '/graph',
  },
]

export default function HomePage() {
  const nav = useNavigate()
  return (
    <div className="home">
      <div className="home-hero">
        <div className="hero-badge">WisOps V1.5</div>
        <h1 className="hero-title">智能运维知识融合平台</h1>
        <p className="hero-sub">将 AI 知识库检索与故障图谱融合，让运维经验沉淀为可查询的结构化知识。</p>
      </div>

      <div className="home-cards">
        {CARDS.map((c) => (
          <button key={c.to} className={`hcard hcard-${c.color}`} onClick={() => nav(c.to)}>
            <div className={`hcard-icon hcard-icon-${c.color}`}>{c.icon}</div>
            <div className="hcard-body">
              <div className="hcard-title">{c.title}</div>
              <div className="hcard-desc">{c.desc}</div>
              <div className="hcard-tags">
                {c.tags.map((t) => <span key={t} className="hcard-tag">{t}</span>)}
              </div>
            </div>
            <span className="hcard-arrow">→</span>
          </button>
        ))}
      </div>

      <div className="home-links">
        <a href="/graph-api/docs" target="_blank" rel="noreferrer">Graph API 文档 ↗</a>
      </div>
    </div>
  )
}
