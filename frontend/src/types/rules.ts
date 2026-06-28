export type RuleAction = 'allow' | 'block' | 'require_approval';
export type RuleType = 'exact' | 'glob' | 'regex';
export type RuleScope = 'global' | 'conversation';
export type ConstraintType =
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'not_contains'
  | 'starts_with'
  | 'ends_with'
  | 'regex'
  | 'in'
  | 'not_in'
  | 'path_prefix';

export interface ArgumentConstraintPayload {
  field: string;
  constrainttype: ConstraintType;
  value: unknown;
  allowrewrite: boolean;
  rewritevalue: unknown | null;
  description: string | null;
}

export interface RuleCreateRequest {
  name: string;
  action: RuleAction;
  toolpattern: string;
  ruletype: RuleType;
  priority: number;
  enabled: boolean;
  constraints: ArgumentConstraintPayload[];
  approvaltimeoutseconds: number;
  reason: string | null;
  description: string | null;
  scope: RuleScope;
  scopeid: string | null;
}

export type RuleCreate = RuleCreateRequest;
export interface RuleUpdateRequest extends RuleCreateRequest {}
export type RuleUpdate = RuleUpdateRequest;

export interface RuleResponse {
  id: string;
  name: string;
  action: RuleAction;
  toolpattern: string;
  ruletype: RuleType;
  priority: number;
  enabled: boolean;
  constraints: ArgumentConstraintPayload[];
  approvaltimeoutseconds: number;
  reason: string | null;
  description: string | null;
  scope: RuleScope;
  scopeid: string | null;
  createdat: string;
  updatedat: string;
}
