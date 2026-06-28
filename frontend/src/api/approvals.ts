import { apiClient } from './client';
import type {
  ApprovalDecisionRequest,
  ApprovalRequest,
} from '../types/approvals';

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
    const response = await apiClient.get<ApprovalRequest[]>('/approvals/pending');
    return response.data;
  } catch {
    return mockApprovals.filter(a => a.status === 'pending');
  }
}

export async function listAllApprovals(): Promise<ApprovalRequest[]> {
  try {
    const response = await apiClient.get<ApprovalRequest[]>('/approvals');
    return response.data;
  } catch {
    return mockApprovals;
  }
}

export async function approveRequest(
  approvalId: string,
  payload: ApprovalDecisionRequest,
): Promise<ApprovalRequest> {
  try {
    const response = await apiClient.post<ApprovalRequest>(
      `/approvals/${approvalId}/approve`,
      payload,
    );
    return response.data;
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
    const response = await apiClient.post<ApprovalRequest>(
      `/approvals/${approvalId}/reject`,
      payload,
    );
    return response.data;
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
