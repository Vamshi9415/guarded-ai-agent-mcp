import { apiClient } from "./client";
import type {
  BudgetResponse,
  BudgetStateResponse,
  BudgetUpdateRequest,
} from "../types/budgets";

export async function getDefaultBudget(): Promise<BudgetResponse> {
  const response = await apiClient.get<BudgetResponse>("/budgets/default");
  return response.data;
}

export async function setDefaultBudget(
  payload: BudgetUpdateRequest,
): Promise<BudgetResponse> {
  const response = await apiClient.put<BudgetResponse>("/budgets/default", payload);
  return response.data;
}

export async function getConversationBudget(
  conversationId: string,
): Promise<BudgetResponse> {
  const response = await apiClient.get<BudgetResponse>(
    `/budgets/${conversationId}`,
  );
  return response.data;
}

export async function setConversationBudget(
  conversationId: string,
  payload: BudgetUpdateRequest,
): Promise<BudgetResponse> {
  const response = await apiClient.put<BudgetResponse>(
    `/budgets/${conversationId}`,
    payload,
  );
  return response.data;
}

export async function getConversationBudgetState(
  conversationId: string,
): Promise<BudgetStateResponse> {
  const response = await apiClient.get<BudgetStateResponse>(
    `/budgets/${conversationId}/state`,
  );
  return response.data;
}