import { apiClient } from './client';
import type {
  RuleCreateRequest,
  RuleResponse,
  RuleUpdateRequest,
} from '../types/rules';

type ApiRuleRequest = {
  name: string;
  action: RuleCreateRequest['action'];
  tool_pattern: string;
  rule_type: RuleCreateRequest['ruletype'];
  priority: number;
  enabled: boolean;
  constraints: RuleCreateRequest['constraints'];
  approval_timeout_seconds: number;
  reason: string | null;
  description: string | null;
  scope: RuleCreateRequest['scope'];
  scope_id: string | null;
};

type ApiRuleResponse = {
  id: string;
  name: string;
  action: RuleResponse['action'];
  tool_pattern: string;
  rule_type: RuleResponse['ruletype'];
  priority: number;
  enabled: boolean;
  constraints: RuleResponse['constraints'];
  approval_timeout_seconds: number;
  reason: string | null;
  description: string | null;
  scope: RuleResponse['scope'];
  scope_id: string | null;
  created_at: string;
  updated_at: string;
};

function toFrontendRule(rule: ApiRuleResponse): RuleResponse {
  return {
    id: rule.id,
    name: rule.name,
    action: rule.action,
    toolpattern: rule.tool_pattern,
    ruletype: rule.rule_type,
    priority: rule.priority,
    enabled: rule.enabled,
    constraints: rule.constraints,
    approvaltimeoutseconds: rule.approval_timeout_seconds,
    reason: rule.reason,
    description: rule.description,
    scope: rule.scope,
    scopeid: rule.scope_id,
    createdat: rule.created_at,
    updatedat: rule.updated_at,
  };
}

function toBackendRule(payload: RuleCreateRequest | RuleUpdateRequest): ApiRuleRequest {
  return {
    name: payload.name,
    action: payload.action,
    tool_pattern: payload.toolpattern,
    rule_type: payload.ruletype,
    priority: payload.priority,
    enabled: payload.enabled,
    constraints: payload.constraints,
    approval_timeout_seconds: payload.approvaltimeoutseconds,
    reason: payload.reason,
    description: payload.description,
    scope: payload.scope,
    scope_id: payload.scopeid,
  };
}

// Mock data when backend unavailable
const MOCK_RULES: RuleResponse[] = [
  {
    id: 'rule-001',
    name: 'Block sensitive file reads',
    action: 'block',
    toolpattern: 'read_file',
    ruletype: 'exact',
    priority: 1,
    enabled: true,
    constraints: [],
    approvaltimeoutseconds: 60,
    reason: 'Prevents unauthorized file reads',
    description: 'Blocks all read_file tool calls',
    scope: 'global',
    scopeid: null,
    createdat: new Date(Date.now() - 86400000).toISOString(),
    updatedat: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'rule-002',
    name: 'Require approval for shell commands',
    action: 'require_approval',
    toolpattern: 'run_*',
    ruletype: 'glob',
    priority: 2,
    enabled: true,
    constraints: [],
    approvaltimeoutseconds: 120,
    reason: 'Shell commands need human review',
    description: 'Requires human approval for any tool matching run_*',
    scope: 'global',
    scopeid: null,
    createdat: new Date(Date.now() - 172800000).toISOString(),
    updatedat: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'rule-003',
    name: 'Allow web search',
    action: 'allow',
    toolpattern: 'web_search',
    ruletype: 'exact',
    priority: 5,
    enabled: false,
    constraints: [],
    approvaltimeoutseconds: 60,
    reason: null,
    description: 'Permits web search tool without restriction',
    scope: 'global',
    scopeid: null,
    createdat: new Date(Date.now() - 259200000).toISOString(),
    updatedat: new Date(Date.now() - 259200000).toISOString(),
  },
];

let mockRules = [...MOCK_RULES];

export async function listRules(): Promise<RuleResponse[]> {
  try {
    const response = await apiClient.get<ApiRuleResponse[]>('/rules');
    return response.data.map((rule) => toFrontendRule(rule));
  } catch {
    return mockRules;
  }
}

export async function getRule(ruleId: string): Promise<RuleResponse> {
  try {
    const response = await apiClient.get<ApiRuleResponse>(`/rules/${ruleId}`);
    return toFrontendRule(response.data);
  } catch {
    const rule = mockRules.find(r => r.id === ruleId);
    if (!rule) throw new Error(`Rule ${ruleId} not found`);
    return rule;
  }
}

export async function createRule(payload: RuleCreateRequest): Promise<RuleResponse> {
  try {
    const response = await apiClient.post<ApiRuleResponse>('/rules', toBackendRule(payload));
    return toFrontendRule(response.data);
  } catch {
    const newRule: RuleResponse = {
      ...payload,
      id: `rule-${Date.now()}`,
      createdat: new Date().toISOString(),
      updatedat: new Date().toISOString(),
    };
    mockRules.push(newRule);
    return newRule;
  }
}

export async function updateRule(ruleId: string, payload: RuleUpdateRequest): Promise<RuleResponse> {
  try {
    const response = await apiClient.put<ApiRuleResponse>(`/rules/${ruleId}`, toBackendRule(payload));
    return toFrontendRule(response.data);
  } catch {
    const idx = mockRules.findIndex(r => r.id === ruleId);
    if (idx === -1) throw new Error(`Rule ${ruleId} not found`);
    const updated: RuleResponse = { ...mockRules[idx], ...payload, updatedat: new Date().toISOString() };
    mockRules[idx] = updated;
    return updated;
  }
}

export async function deleteRule(ruleId: string): Promise<void> {
  try {
    await apiClient.delete(`/rules/${ruleId}`);
  } catch {
    mockRules = mockRules.filter(r => r.id !== ruleId);
  }
}
