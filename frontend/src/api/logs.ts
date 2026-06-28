import { apiClient } from './client';
import type { LogEntry } from '../types/logs';

const MOCK_LOGS: LogEntry[] = [
  {
    conversation_id: 'conv-001',
    tool_name: 'read_file',
    arguments: { path: '/etc/passwd' },
    outcome: 'denied',
    timestamp: new Date(Date.now() - 120000).toISOString(),
    execution_time_ms: 12.4,
    rewritten_arguments: null,
    reason: 'Blocked by rule: Block sensitive file reads',
    matched_rule_id: 'rule-001',
    engine_failure: false,
  },
  {
    conversation_id: 'conv-002',
    tool_name: 'web_search',
    arguments: { query: 'weather today' },
    outcome: 'allowed',
    timestamp: new Date(Date.now() - 300000).toISOString(),
    execution_time_ms: 8.1,
    rewritten_arguments: null,
    reason: null,
    matched_rule_id: null,
    engine_failure: false,
  },
  {
    conversation_id: 'conv-001',
    tool_name: 'run_shell_command',
    arguments: { command: 'ls -la' },
    outcome: 'requires_approval',
    timestamp: new Date(Date.now() - 60000).toISOString(),
    execution_time_ms: 5.3,
    rewritten_arguments: null,
    reason: 'Requires human approval per policy rule',
    matched_rule_id: 'rule-002',
    engine_failure: false,
  },
  {
    conversation_id: 'conv-003',
    tool_name: 'write_file',
    arguments: { path: '/tmp/output.txt', content: 'hello world' },
    outcome: 'allowed',
    timestamp: new Date(Date.now() - 900000).toISOString(),
    execution_time_ms: 15.7,
    rewritten_arguments: null,
    reason: null,
    matched_rule_id: null,
    engine_failure: false,
  },
];

export async function listLogs(conversationId?: string): Promise<LogEntry[]> {
  try {
    const response = await apiClient.get<LogEntry[]>('/logs', {
      params: conversationId ? { conversation_id: conversationId } : undefined,
    });
    return response.data;
  } catch {
    if (conversationId) {
      return MOCK_LOGS.filter(l => l.conversation_id === conversationId);
    }
    return MOCK_LOGS;
  }
}
