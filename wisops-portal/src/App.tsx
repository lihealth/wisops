import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import HomePage      from './pages/HomePage'
import ChatPage      from './pages/ChatPage'
import GraphPage     from './pages/GraphPage'
import ExtractPage   from './pages/ExtractPage'
import DashboardPage from './pages/DashboardPage'
import SopPage       from './pages/SopPage'
import './App.css'

const NAV = [
  { to: '/',          icon: '🏠', label: '首页' },
  { to: '/chat',      icon: '🤖', label: 'AI 问答' },
  { to: '/graph',     icon: '🕸️', label: '图谱管理' },
  { to: '/extract',   icon: '📥', label: '知识抽取' },
  { to: '/sop',       icon: '📋', label: 'SOP 管理' },
  { to: '/dashboard', icon: '📊', label: '运营看板' },
]

export default function App() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">⚙️</span>
          <span className="logo-text">WisOps</span>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
            >
              <span className="nav-icon">{icon}</span>
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="version">V1.7</span>
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/"          element={<HomePage />} />
          <Route path="/chat"      element={<ChatPage />} />
          <Route path="/graph"     element={<GraphPage />} />
          <Route path="/extract"   element={<ExtractPage />} />
          <Route path="/sop"       element={<SopPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="*"          element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
