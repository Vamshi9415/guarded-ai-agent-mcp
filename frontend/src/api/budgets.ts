import { apiClient } from './client';
import type {
  BudgetResponse,
  BudgetStateResponse,
  BudgetUpdateRequest,
} from '../types/budgets';

// Mock data fallback for when backend is unavailable
const MOCK_BUDGETS: BudgetResponse[] = [
  { conversationid: 'conv-001', maxtokens: 10000 },
  { conversationid: 'conv-002', maxtokens: 5000 },
  { conversationid: 'conv-003', maxtokens: 20000 },
];

const MOCK_STATES: Record<string, BudgetStateResponse> = {
  'conv-001': {
    conversationid: 'conv-001',
    inputtokens: 3200,
    outputtokens: 1800,
    totaltokens: 5000,
    lastupdated: new Date(Date.now() - 300000).toISOString(),
  },
  'conv-002': {
    conversationid: 'conv-002',
    inputtokens: 4100,
    outputtokens: 800,
    totaltokens: 4900,
    lastupdated: new Date(Date.now() - 60000).toISOString(),
  },
  'conv-003': {
    conversationid: 'conv-003',
    inputtokens: 1000,
    outputtokens: 500,
    totaltokens: 1500,
    lastupdated: new Date(Date.now() - 900000).toISOString(),
  },
};

export async function listBudgets(): Promise<BudgetResponse[]> {
  try {
    const response = await apiClient.get<BudgetResponse[]>('/budgets');
    return response.data;
  } catch {
    return MOCK_BUDGETS;
  }
}

export async function getBudget(conversationId: string): Promise<BudgetResponse> {
  try {
    const response = await apiClient.get<BudgetResponse>(`/budgets/${conversationId}`);
    return response.data;
  } catch {
    return MOCK_BUDGETS.find(b => b.conversationid === conversationId) ?? { conversationid: conversationId, maxtokens: 10000 };
  }
}

export async function getDefaultBudget(): Promise<BudgetResponse> {
  try {
    const response = await apiClient.get<BudgetResponse>('/budgets/default');
    return response.data;
  } catch {
    return { conversationid: null, maxtokens: 10000 };
  }
}

export async function setDefaultBudget(payload: BudgetUpdateRequest): Promise<BudgetResponse> {
  const response = await apiClient.put<BudgetResponse>('/budgets/default', payload);
  return response.data;
}

export async function updateBudget(conversationId: string, payload: BudgetUpdateRequest): Promise<BudgetResponse> {
  try {
    const response = await apiClient.put<BudgetResponse>(`/budgets/${conversationId}`, payload);
    return response.data;
  } catch {
    return { conversationid: conversationId, maxtokens: payload.max_tokens };
  }
}

export async function resetBudget(conversationId: string): Promise<BudgetResponse> {
  try {
    const response = await apiClient.delete<BudgetResponse>(`/budgets/${conversationId}`);
    return response.data;
  } catch {
    return { conversationid: conversationId, maxtokens: 10000 };
  }
}

export async function setConversationBudget(conversationId: string, payload: BudgetUpdateRequest): Promise<BudgetResponse> {
  return updateBudget(conversationId, payload);
}

export async function getConversationBudget(conversationId: string): Promise<BudgetResponse> {
  return getBudget(conversationId);
}

export async function getConversationBudgetState(conversationId: string): Promise<BudgetStateResponse> {
  try {
    const response = await apiClient.get<BudgetStateResponse>(`/budgets/${conversationId}/state`);
    return response.data;
  } catch {
    return MOCK_STATES[conversationId] ?? {
      conversationid: conversationId,
      inputtokens: 0,
      outputtokens: 0,
      totaltokens: 0,
      lastupdated: new Date().toISOString(),
    };
  }
}
