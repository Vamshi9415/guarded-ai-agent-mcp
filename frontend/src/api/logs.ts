import { apiClient } from "./client";
import type { LogEntry } from "../types/logs";

export async function listLogs(
  conversationId?: string,
): Promise<LogEntry[]> {
  const response = await apiClient.get<LogEntry[]>("/logs", {
    params: conversationId ? { conversationid: conversationId } : undefined,
  });

  return response.data;
}