import type { ApiDateTimeString, ApiId, ApiStatus } from './common'

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "timedout";

export interface ApprovalRequest {
  id: string;
  conversationid: string;
  toolname: string;
  arguments: Record<string, unknown>;
  matchedruleid: string;
  expiresat: string;
  status: ApprovalStatus;
  createdat: string;
  resolvedat: string | null;
  resolvedby: string | null;
  resolutionreason: string | null;
}

export interface ApprovalDecisionRequest {
  approver: string;
  reason?: string | null;
}