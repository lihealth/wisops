import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { RoleProvider, useRole, type Role } from './RoleContext'
import HomePage      from './pages/HomePage'
import ChatPage      from './pages/ChatPage'
import GraphPage     from './pages/GraphPage'
import ExtractPage   from './pages/ExtractPage'
import DashboardPage from './pages/DashboardPage'
import SopPage       from './pages/SopPage'
import AssetsPage    from './pages/AssetsPage'
import IncidentPage  from './pages/IncidentPage'
import './App.css'

interface NavItem {
  to: string
  icon: string
  label: string
  /** 需要拥有此操作权限才在侧栏显示，不填则始终显示 */
  requireAction?: import('./RoleContext').Action
}

const NAV: NavItem[] = [
  { to: '/',          icon: '🏠', label: '首页' },
  { to: '/chat',      icon: '🤖', label: 'AI 问答' },
  { to: '/graph',     icon: '🕸️', label: '图谱管理' },
  { to: '/assets',    icon: '🖥️', label: '资产管理' },
  { to: '/incidents', icon: '🎫', label: '工单沉淀', requireAction: 'write_incident' },
  { to: '/extract',   icon: '📥', label: '知识抽取', requireAction: 'view_extract' },
  { to: '/sop',       icon: '📋', label: 'SOP 管理', requireAction: 'manage_sop' },
  { to: '/dashboard', icon: '📊', label: '运营看板', requireAction: 'view_dashboard' },
]

const ROLE_LABELS: Record<Role, string> = {
  admin:    '🔑 管理员',
  engineer: '🔧 运维工程师',
  readonly: '👁️ 只读',
}

function Shell() {
  const { role, setRole, can } = useRole()

  const visibleNav = NAV.filter(n => !n.requireAction || can(n.requireAction))

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">⚙️</span>
          <span className="logo-text">WisOps</span>
        </div>
        <nav className="sidebar-nav">
          {visibleNav.map(({ to, icon, label }) => (
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
          <div className="role-switcher">
            <span className="role-label">当前角色</span>
            <select
              className="role-select"
              value={role}
              onChange={e => setRole(e.target.value as Role)}
              title="切换角色（仅限演示环境，生产应通过认证系统分配）"
            >
              {(Object.entries(ROLE_LABELS) as [Role, string][]).map(([r, label]) => (
                <option key={r} value={r}>{label}</option>
              ))}
            </select>
          </div>
          <span className="version">V1.9</span>
        </div>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/"          element={<HomePage />} />
          <Route path="/chat"      element={<ChatPage />} />
          <Route path="/graph"     element={<GraphPage />} />
          <Route path="/assets"    element={<AssetsPage />} />
          <Route path="/incidents" element={
            can('write_incident') ? <IncidentPage /> : <AccessDenied />
          } />
          <Route path="/extract"   element={
            can('view_extract') ? <ExtractPage /> : <AccessDenied />
          } />
          <Route path="/sop"       element={
            can('manage_sop') ? <SopPage /> : <AccessDenied />
          } />
          <Route path="/dashboard" element={
            can('view_dashboard') ? <DashboardPage /> : <AccessDenied />
          } />
          <Route path="*"          element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function AccessDenied() {
  const { role } = useRole()
  return (
    <div className="access-denied">
      <div className="access-denied-icon">🔒</div>
      <div className="access-denied-title">权限不足</div>
      <div className="access-denied-desc">
        当前角色「{ROLE_LABELS[role]}」无法访问此页面。<br />
        如需访问，请在左下角切换为更高权限角色。
      </div>
    </div>
  )
}

export default function App() {
  return (
    <RoleProvider>
      <Shell />
    </RoleProvider>
  )
}
