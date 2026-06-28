import { apiClient } from './client';
import type {
  BudgetResponse,
  BudgetStateResponse,
  BudgetUpdateRequest,
} from '../types/budgets';

type ApiBudgetResponse = {
  conversation_id: string | null;
  max_tokens: number;
};

type ApiBudgetStateResponse = {
  conversation_id: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  last_updated: string;
};

function toFrontendBudget(budget: ApiBudgetResponse): BudgetResponse {
  return {
    conversationid: budget.conversation_id,
    maxtokens: budget.max_tokens,
  };
}

function toFrontendBudgetState(state: ApiBudgetStateResponse): BudgetStateResponse {
  return {
    conversationid: state.conversation_id,
    inputtokens: state.input_tokens,
    outputtokens: state.output_tokens,
    totaltokens: state.total_tokens,
    lastupdated: state.last_updated,
  };
}

function toBackendBudget(payload: BudgetUpdateRequest) {
  return { max_tokens: payload.max_tokens };
}

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
    const response = await apiClient.get<ApiBudgetResponse[]>('/budgets');
    return response.data.map(toFrontendBudget);
  } catch {
    return MOCK_BUDGETS;
  }
}

export async function getBudget(conversationId: string): Promise<BudgetResponse> {
  try {
    const response = await apiClient.get<ApiBudgetResponse>(`/budgets/${conversationId}`);
    return toFrontendBudget(response.data);
  } catch {
    return MOCK_BUDGETS.find(b => b.conversationid === conversationId) ?? { conversationid: conversationId, maxtokens: 10000 };
  }
}

export async function getDefaultBudget(): Promise<BudgetResponse> {
  try {
    const response = await apiClient.get<ApiBudgetResponse>('/budgets/default');
    return toFrontendBudget(response.data);
  } catch {
    return { conversationid: null, maxtokens: 10000 };
  }
}

export async function setDefaultBudget(payload: BudgetUpdateRequest): Promise<BudgetResponse> {
  const response = await apiClient.put<ApiBudgetResponse>('/budgets/default', toBackendBudget(payload));
  return toFrontendBudget(response.data);
}

export async function updateBudget(conversationId: string, payload: BudgetUpdateRequest): Promise<BudgetResponse> {
  try {
    const response = await apiClient.put<ApiBudgetResponse>(`/budgets/${conversationId}`, toBackendBudget(payload));
    return toFrontendBudget(response.data);
  } catch {
    return { conversationid: conversationId, maxtokens: payload.max_tokens };
  }
}

export async function resetBudget(conversationId: string): Promise<BudgetResponse> {
  try {
    const response = await apiClient.delete<ApiBudgetResponse>(`/budgets/${conversationId}`);
    return toFrontendBudget(response.data);
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
    const response = await apiClient.get<ApiBudgetStateResponse>(`/budgets/${conversationId}/state`);
    return toFrontendBudgetState(response.data);
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
