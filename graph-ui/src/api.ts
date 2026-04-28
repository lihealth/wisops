const BASE = '/api'

export interface Solution {
  id: string
  name: string
  description: string
}

export interface HealthResult {
  status: string
  hugegraph: string
}

export interface AddResult {
  status: string
  edge_status: 'created' | 'exists'
}

export interface QueryResult {
  fault_name: string
  solutions: Solution[]
  count: number
}

export interface FaultsResult {
  faults: string[]
  count: number
}

export async function getHealth(): Promise<HealthResult> {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error('服务不可达')
  return res.json()
}

export async function addRelation(
  fault_name: string,
  solution_name: string,
  solution_description: string
): Promise<AddResult> {
  const res = await fetch(`${BASE}/graph/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fault_name, solution_name, solution_description }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail ?? '请求失败')
  }
  return res.json()
}

export async function querySolutions(fault_name: string): Promise<QueryResult> {
  const res = await fetch(`${BASE}/graph/query?fault_name=${encodeURIComponent(fault_name)}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '查询失败' }))
    throw new Error(err.detail ?? '查询失败')
  }
  return res.json()
}

export async function getFaults(): Promise<FaultsResult> {
  const res = await fetch(`${BASE}/graph/faults`)
  if (!res.ok) return { faults: [], count: 0 }
  return res.json()
}
