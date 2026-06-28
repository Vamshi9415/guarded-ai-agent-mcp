export type DecisionOutcome =
  | 'allowed'
  | 'denied'
  | 'requires_approval'
  | 'error';

export interface LogEntry {
  conversation_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  outcome: string;
  timestamp: string;
  execution_time_ms: number;
  rewritten_arguments?: Record<string, unknown> | null;
  reason?: string | null;
  matched_rule_id?: string | null;
  engine_failure: boolean;
}
