import { apiClient } from './client'
import type {
  ApprovalDecisionRequest,
  ApprovalRequest,
} from '../types/approvals'

export async function listPendingApprovals(): Promise<ApprovalRequest[]> {
  const response = await apiClient.get<ApprovalRequest[]>('/approvals/pending')
  return response.data
}

export async function approveRequest(
  approvalId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalRequest> {
  const response = await apiClient.post<ApprovalRequest>(
    `/approvals/${approvalId}/approve`,
    payload,
  )
  return response.data
}

export async function rejectRequest(
  approvalId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalRequest> {
  const response = await apiClient.post<ApprovalRequest>(
    `/approvals/${approvalId}/reject`,
    payload,
  )
  return response.data
}
