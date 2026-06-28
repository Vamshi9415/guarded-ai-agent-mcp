import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { approveRequest, listPendingApprovals, rejectRequest } from '../api'
import type { ApprovalDecisionRequest } from '../types/approvals'

export const APPROVALS_QUERY_KEY = ['approvals', 'pending'] as const

export function usePendingApprovals() {
  return useQuery({
    queryKey: APPROVALS_QUERY_KEY,
    queryFn: listPendingApprovals,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    staleTime: 10_000,
  })
}

export function useApproveRequest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      approvalId,
      payload,
    }: {
      approvalId: string
      payload: ApprovalDecisionRequest
    }) => approveRequest(approvalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: APPROVALS_QUERY_KEY })
    },
  })
}

export function useRejectRequest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      approvalId,
      payload,
    }: {
      approvalId: string
      payload: ApprovalDecisionRequest
    }) => rejectRequest(approvalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: APPROVALS_QUERY_KEY })
    },
  })
}
