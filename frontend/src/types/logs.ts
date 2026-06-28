import type { ApiDateTimeString, ApiId, ApiStatus } from './common'

export type DecisionOutcome =
  | "allowed"
  | "denied"
  | "requires_approval"
  | "error";

export interface AuditLogEntry {
  conversationId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  outcome: DecisionOutcome;
  timestamp: string;
  executionTimeMs: number;
  rewrittenArguments?: Record<string, unknown> | null;
  reason?: string | null;
  matchedRuleId?: string | null;
  engineFailure?: boolean;
}

export interface LogEntry {
  conversationid: string;
  toolname: string;
  arguments: Record<string, unknown>;
  outcome: string;
  timestamp: string;
  executiontimems: number;
  rewrittenarguments?: Record<string, unknown> | null;
  reason?: string | null;
  matchedruleid?: string | null;
  enginefailure: boolean;
}