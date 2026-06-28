export type DecisionOutcome =
  | 'allowed'
  | 'denied'
  | 'requires_approval'
  | 'error';

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
