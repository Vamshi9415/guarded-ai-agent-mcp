import { apiClient } from './client';
import type { LogEntry } from '../types/logs';

const MOCK_LOGS: LogEntry[] = [
  {
    conversationid: 'conv-001',
    toolname: 'read_file',
    arguments: { path: '/etc/passwd' },
    outcome: 'denied',
    timestamp: new Date(Date.now() - 120000).toISOString(),
    executiontimems: 12.4,
    rewrittenarguments: null,
    reason: 'Blocked by rule: Block sensitive file reads',
    matchedruleid: 'rule-001',
    enginefailure: false,
  },
  {
    conversationid: 'conv-002',
    toolname: 'web_search',
    arguments: { query: 'weather today' },
    outcome: 'allowed',
    timestamp: new Date(Date.now() - 300000).toISOString(),
    executiontimems: 8.1,
    rewrittenarguments: null,
    reason: null,
    matchedruleid: null,
    enginefailure: false,
  },
  {
    conversationid: 'conv-001',
    toolname: 'run_shell_command',
    arguments: { command: 'ls -la' },
    outcome: 'requires_approval',
    timestamp: new Date(Date.now() - 60000).toISOString(),
    executiontimems: 5.3,
    rewrittenarguments: null,
    reason: 'Requires human approval per policy rule',
    matchedruleid: 'rule-002',
    enginefailure: false,
  },
  {
    conversationid: 'conv-003',
    toolname: 'write_file',
    arguments: { path: '/tmp/output.txt', content: 'hello world' },
    outcome: 'allowed',
    timestamp: new Date(Date.now() - 900000).toISOString(),
    executiontimems: 15.7,
    rewrittenarguments: null,
    reason: null,
    matchedruleid: null,
    enginefailure: false,
  },
];

export async function listLogs(conversationId?: string): Promise<LogEntry[]> {
  try {
    const response = await apiClient.get<LogEntry[]>('/logs', {
      params: conversationId ? { conversationid: conversationId } : undefined,
    });
    return response.data;
  } catch {
    if (conversationId) {
      return MOCK_LOGS.filter(l => l.conversationid === conversationId);
    }
    return MOCK_LOGS;
  }
}
