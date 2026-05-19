import { createContext, useContext, useState, ReactNode } from 'react'

export type Role = 'admin' | 'engineer' | 'readonly'

export interface RoleCtx {
  role: Role
  setRole: (r: Role) => void
  can: (action: Action) => boolean
  /** 返回写操作所需的请求头（自动附带 X-API-Key，若已配置） */
  writeHeaders: (extra?: Record<string, string>) => Record<string, string>
  /** Graph API Key（对应后端 GRAPH_API_KEY 环境变量） */
  apiKey: string
  setApiKey: (k: string) => void
}

/**
 * 操作权限枚举（细粒度）
 *
 * view_*  — 可访问页面/列表（readonly 起始权限）
 * write_* — 可提交表单/录入（engineer+）
 * approve_* — 可审核（admin 专属）
 * manage_* — 可创建/编辑管理类内容（admin 专属）
 */
export type Action =
  | 'view_incident'     // 工单列表与详情
  | 'write_incident'    // 工单录入
  | 'view_extract'      // 知识抽取页（提交 + 查看队列）
  | 'approve_extract'   // 审核抽取队列
  | 'write_graph'       // 图谱录入（POST /graph/add 等）
  | 'manage_sop'        // SOP 新建/编辑
  | 'view_dashboard'    // 运营看板
  | 'view_audit'        // 审计日志页

const PERMISSIONS: Record<Role, Set<Action>> = {
  admin: new Set([
    'view_incident', 'write_incident',
    'view_extract', 'approve_extract',
    'write_graph', 'manage_sop',
    'view_dashboard', 'view_audit',
  ]),
  engineer: new Set([
    'view_incident', 'write_incident',
    'view_extract',
    'write_graph',
  ]),
  readonly: new Set([
    'view_incident',
    'view_dashboard',
  ]),
}

const LS_ROLE = 'wisops_role'
const LS_KEY  = 'wisops_api_key'

function loadRole(): Role {
  const v = localStorage.getItem(LS_ROLE)
  if (v === 'admin' || v === 'engineer' || v === 'readonly') return v
  return 'admin'
}
function loadKey(): string {
  return localStorage.getItem(LS_KEY) ?? ''
}

const Ctx = createContext<RoleCtx>({
  role: 'admin',
  setRole: () => {},
  can: () => true,
  writeHeaders: () => ({ 'Content-Type': 'application/json' }),
  apiKey: '',
  setApiKey: () => {},
})

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState]   = useState<Role>(loadRole)
  const [apiKey, setApiKeyState] = useState<string>(loadKey)

  const setRole = (r: Role) => {
    localStorage.setItem(LS_ROLE, r)
    setRoleState(r)
  }

  const setApiKey = (k: string) => {
    localStorage.setItem(LS_KEY, k)
    setApiKeyState(k)
  }

  const can = (action: Action) => PERMISSIONS[role].has(action)

  const writeHeaders = (extra: Record<string, string> = {}): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json', ...extra }
    if (apiKey.trim()) headers['X-API-Key'] = apiKey.trim()
    return headers
  }

  return (
    <Ctx.Provider value={{ role, setRole, can, writeHeaders, apiKey, setApiKey }}>
      {children}
    </Ctx.Provider>
  )
}

export function useRole() {
  return useContext(Ctx)
}
