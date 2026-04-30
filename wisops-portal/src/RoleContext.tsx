import { createContext, useContext, useState, ReactNode } from 'react'

export type Role = 'admin' | 'engineer' | 'readonly'

export interface RoleCtx {
  role: Role
  setRole: (r: Role) => void
  can: (action: Action) => boolean
}

/**
 * 操作权限枚举
 * - write_graph      : 图谱录入（POST /graph/add、/graph/sop 等写操作）
 * - approve_extract  : 审核抽取队列
 * - manage_sop       : SOP 新建/编辑
 * - view_dashboard   : 运营看板
 * - view_extract     : 知识抽取页（提交 + 审核台）
 * - write_incident   : 工单录入
 * - view_audit       : 审计日志（暂未单独页，保留扩展）
 */
export type Action =
  | 'write_graph'
  | 'approve_extract'
  | 'manage_sop'
  | 'view_dashboard'
  | 'view_extract'
  | 'write_incident'
  | 'view_audit'

const PERMISSIONS: Record<Role, Set<Action>> = {
  admin: new Set([
    'write_graph', 'approve_extract', 'manage_sop',
    'view_dashboard', 'view_extract', 'write_incident', 'view_audit',
  ]),
  engineer: new Set([
    'write_graph', 'view_extract', 'write_incident',
  ]),
  readonly: new Set([]),
}

const LS_KEY = 'wisops_role'

function loadRole(): Role {
  const v = localStorage.getItem(LS_KEY)
  if (v === 'admin' || v === 'engineer' || v === 'readonly') return v
  return 'admin'
}

const Ctx = createContext<RoleCtx>({
  role: 'admin',
  setRole: () => {},
  can: () => true,
})

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(loadRole)

  const setRole = (r: Role) => {
    localStorage.setItem(LS_KEY, r)
    setRoleState(r)
  }

  const can = (action: Action) => PERMISSIONS[role].has(action)

  return <Ctx.Provider value={{ role, setRole, can }}>{children}</Ctx.Provider>
}

export function useRole() {
  return useContext(Ctx)
}
