import { apiClient } from './client'
import type { ToolResponse } from '../types/tools'

const MOCK_TOOLS: ToolResponse[] = [
  { name: 'read_file', description: 'Read file contents from the workspace', server_name: 'local-crud' },
  { name: 'write_file', description: 'Write content to a file', server_name: 'local-crud' },
  { name: 'web_search', description: 'Search the internet', server_name: 'context7' },
]

let mockTools = [...MOCK_TOOLS]

export async function listTools(): Promise<ToolResponse[]> {
  try {
    const response = await apiClient.get<ToolResponse[]>('/tools')
    return response.data
  } catch {
    return mockTools
  }
}