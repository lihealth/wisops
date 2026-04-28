import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import AddFault from './pages/AddFault'
import QueryFault from './pages/QueryFault'
import { getHealth } from './api'
import './App.css'

export default function App() {
  const [health, setHealth] = useState<'ok' | 'degraded' | 'checking'>('checking')

  useEffect(() => {
    getHealth()
      .then((r) => setHealth(r.status === 'ok' ? 'ok' : 'degraded'))
      .catch(() => setHealth('degraded'))
  }, [])

  const dot = health === 'ok' ? '🟢' : health === 'degraded' ? '🔴' : '⏳'
  const label = health === 'ok' ? '图谱服务正常' : health === 'degraded' ? '图谱服务异常' : '检测中...'

  return (
    <div className="layout">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚙️</span>
            <span className="logo-text">WisOps 图谱管理</span>
          </div>
          <nav className="nav">
            <NavLink to="/add" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              录入故障
            </NavLink>
            <NavLink to="/query" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              查询方案
            </NavLink>
          </nav>
          <div className="health-badge">
            <span>{dot}</span>
            <span className="health-label">{label}</span>
          </div>
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/query" replace />} />
          <Route path="/add" element={<AddFault />} />
          <Route path="/query" element={<QueryFault />} />
        </Routes>
      </main>

      <footer className="footer">
        WisOps V1.0 · 智能运维知识平台 ·{' '}
        <a href="http://localhost:8090" target="_blank" rel="noreferrer">Dify 知识库</a>
        {' · '}
        <a href="/graph-api/docs" target="_blank" rel="noreferrer">API 文档</a>
      </footer>
    </div>
  )
}
