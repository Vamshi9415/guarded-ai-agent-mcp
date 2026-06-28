import { apiClient } from './client';
import type {
  ApprovalDecisionRequest,
  ApprovalRequest,
} from '../types/approvals';

type ApiApprovalRequest = {
  id: string;
  conversation_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  matched_rule_id: string;
  expires_at: string;
  status: ApprovalRequest['status'];
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_reason: string | null;
};

type ApprovalStatusValue = ApprovalRequest['status'];

function normalizeApprovalStatus(status: string): ApprovalStatusValue {
  const normalized = status.toLowerCase();

  if (normalized === 'pending' || normalized === 'approved' || normalized === 'rejected' || normalized === 'timedout') {
    return normalized;
  }

  return 'pending';
}

type ApiApprovalDecisionRequest = {
  resolved_by: string;
  reason?: string | null;
};

function toFrontendApproval(approval: ApiApprovalRequest): ApprovalRequest {
  return {
    id: approval.id,
    conversationid: approval.conversation_id,
    toolname: approval.tool_name,
    arguments: approval.arguments,
    matchedruleid: approval.matched_rule_id,
    expiresat: approval.expires_at,
    status: normalizeApprovalStatus(approval.status),
    createdat: approval.created_at,
    resolvedat: approval.resolved_at,
    resolvedby: approval.resolved_by,
    resolutionreason: approval.resolution_reason,
  };
}

function toBackendDecision(payload: ApprovalDecisionRequest): ApiApprovalDecisionRequest {
  return {
    resolved_by: payload.approver,
    reason: payload.reason ?? null,
  };
}

// Mock data for when backend is unavailable
const MOCK_APPROVALS: ApprovalRequest[] = [
  {
    id: 'appr-001',
    conversationid: 'conv-001',
    toolname: 'run_shell_command',
    arguments: { command: 'rm -rf /tmp/cache', shell: true },
    matchedruleid: 'rule-002',
    expiresat: new Date(Date.now() + 300000).toISOString(),
    status: 'pending',
    createdat: new Date(Date.now() - 60000).toISOString(),
    resolvedat: null,
    resolvedby: null,
    resolutionreason: null,
  },
  {
    id: 'appr-002',
    conversationid: 'conv-002',
    toolname: 'write_file',
    arguments: { path: '/etc/hosts', content: '127.0.0.1 malicious.site' },
    matchedruleid: 'rule-001',
    expiresat: new Date(Date.now() + 120000).toISOString(),
    status: 'pending',
    createdat: new Date(Date.now() - 180000).toISOString(),
    resolvedat: null,
    resolvedby: null,
    resolutionreason: null,
  },
];

let mockApprovals = [...MOCK_APPROVALS];

export async function listPendingApprovals(): Promise<ApprovalRequest[]> {
  try {
    const response = await apiClient.get<ApiApprovalRequest[]>('/approvals/pending');
    return response.data.map(toFrontendApproval);
  } catch {
    return mockApprovals.filter(a => a.status === 'pending');
  }
}

export async function listAllApprovals(): Promise<ApprovalRequest[]> {
  try {
    const response = await apiClient.get<ApiApprovalRequest[]>('/approvals');
    return response.data.map(toFrontendApproval);
  } catch {
    return mockApprovals;
  }
}

export async function approveRequest(
  approvalId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalRequest> {
  try {
    const response = await apiClient.post<ApiApprovalRequest>(
      `/approvals/${approvalId}/approve`,
      toBackendDecision(payload),
    );
    return toFrontendApproval(response.data);
  } catch {
    const idx = mockApprovals.findIndex(a => a.id === approvalId);
    if (idx !== -1) {
      mockApprovals[idx] = {
        ...mockApprovals[idx],
        status: 'approved',
        resolvedat: new Date().toISOString(),
        resolvedby: payload.approver,
        resolutionreason: payload.reason ?? null,
      };
      return mockApprovals[idx];
    }
    throw new Error(`Approval ${approvalId} not found`);
  }
}

export async function rejectRequest(
  approvalId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalRequest> {
  try {
    const response = await apiClient.post<ApiApprovalRequest>(
      `/approvals/${approvalId}/reject`,
      toBackendDecision(payload),
    );
    return toFrontendApproval(response.data);
  } catch {
    const idx = mockApprovals.findIndex(a => a.id === approvalId);
    if (idx !== -1) {
      mockApprovals[idx] = {
        ...mockApprovals[idx],
        status: 'rejected',
        resolvedat: new Date().toISOString(),
        resolvedby: payload.approver,
        resolutionreason: payload.reason ?? null,
      };
      return mockApprovals[idx];
    }
    throw new Error(`Approval ${approvalId} not found`);
  }
}
