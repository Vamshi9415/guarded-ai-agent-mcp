export type HealthStatus = string

export interface HealthResponse {
  status: HealthStatus
  rules: number
  pending_approvals: number
  version: string
}