import { apiClient } from "./client";

import type {
  RuleCreateRequest,
  RuleResponse,
  RuleUpdateRequest,
} from "../types/rules";

export async function listRules(): Promise<RuleResponse[]> {
  const response = await apiClient.get<RuleResponse[]>("/rules");
  return response.data;
}

export async function getRule(ruleId: string): Promise<RuleResponse> {
  const response = await apiClient.get<RuleResponse>(`/rules/${ruleId}`);
  return response.data;
}

export async function createRule(
  payload: RuleCreateRequest,
): Promise<RuleResponse> {
  const response = await apiClient.post<RuleResponse>("/rules", payload);
  return response.data;
}

export async function updateRule(
  ruleId: string,
  payload: RuleUpdateRequest,
): Promise<RuleResponse> {
  const response = await apiClient.put<RuleResponse>(`/rules/${ruleId}`, payload);
  return response.data;
}

export async function deleteRule(ruleId: string): Promise<void> {
  await apiClient.delete(`/rules/${ruleId}`);
}