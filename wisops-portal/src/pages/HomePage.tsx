import { useNavigate } from 'react-router-dom'
import './HomePage.css'

const CARDS = [
  {
    icon: '🤖', color: 'blue', title: 'AI 智能问答',
    desc: '基于 RAG + 图谱融合的知识问答，支持流式输出、多轮对话，自动检索图谱上下文增强回答。',
    tags: ['Graph-RAG', '流式输出', '多轮对话'],
    to: '/chat',
  },
  {
    icon: '🕸️', color: 'green', title: '故障图谱管理',
    desc: '基于 HugeGraph 的全链路知识图谱，录入故障关系，查询方案，SVG 可视化子图。',
    tags: ['知识图谱', '故障录入', '方案查询', '可视化'],
    to: '/graph',
  },
  {
    icon: '📥', color: 'purple', title: '知识抽取',
    desc: '上传 SOP 或运维文档，AI 自动抽取故障–方案知识条目，经审核后写入图谱，实现知识闭环沉淀。',
    tags: ['LLM 抽取', '人工审核', '自动沉淀'],
    to: '/extract',
  },
  {
    icon: '📋', color: 'orange', title: 'SOP 管理',
    desc: '创建、编辑标准处置步骤文档（SOP），关联到具体故障类型，支持版本管理与步骤展开查阅。',
    tags: ['标准流程', '步骤管理', '版本控制'],
    to: '/sop',
  },
  {
    icon: '📊', color: 'cyan', title: '运营看板',
    desc: '实时展示图谱节点分布、知识覆盖率、方案复用率、抽取转化率等核心运营指标。',
    tags: ['覆盖率', 'MTTR', '数据分析'],
    to: '/dashboard',
  },
]

export default function HomePage() {
  const nav = useNavigate()
  return (
    <div className="home">
      <div className="home-hero">
        <div className="hero-badge">WisOps V1.7</div>
        <h1 className="hero-title">智能运维知识融合平台</h1>
        <p className="hero-sub">
          将 AI 知识库检索、故障图谱推理与知识自动沉淀融合，<br />
          让运维经验从「个人记忆」变为「可查询的结构化知识」。
        </p>
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
        <a href="http://localhost:8281" target="_blank" rel="noreferrer">Dify 控制台 ↗</a>
        <a href="http://localhost:8081" target="_blank" rel="noreferrer">HugeGraph Studio ↗</a>
      </div>
    </div>
  )
}
