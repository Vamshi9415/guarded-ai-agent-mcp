export interface BudgetUpdateRequest {
  max_tokens: number;
}

export interface BudgetResponse {
  conversationid: string | null;
  maxtokens: number;
}

export interface BudgetStateResponse {
  conversationid: string;
  inputtokens: number;
  outputtokens: number;
  totaltokens: number;
  lastupdated: string;
}