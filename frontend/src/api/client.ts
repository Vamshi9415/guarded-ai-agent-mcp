import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from 'axios'

const DEFAULT_API_BASE_URL = '/api'
const DEFAULT_TIMEOUT_MS = 15_000

export interface ApiErrorPayload {
  detail?: unknown
  message?: unknown
  error?: unknown
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number | null
  readonly data: unknown
  readonly isNetworkError: boolean
  readonly isTimeoutError: boolean
  readonly code?: string

  constructor(
    message: string,
    options?: {
      status?: number | null
      data?: unknown
      isNetworkError?: boolean
      isTimeoutError?: boolean
      code?: string
    },
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = options?.status ?? null
    this.data = options?.data
    this.isNetworkError = options?.isNetworkError ?? false
    this.isTimeoutError = options?.isTimeoutError ?? false
    this.code = options?.code
  }
}

function getApiBaseUrl() {
  const env = import.meta as ImportMeta & {
    env?: {
      VITE_API_BASE_URL?: string
    }
  }

  return env.env?.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
}

function extractErrorMessage(data: unknown): string | null {
  if (!data || typeof data !== 'object') {
    return null
  }

  const candidate = data as ApiErrorPayload

  if (typeof candidate.message === 'string' && candidate.message.trim()) {
    return candidate.message
  }

  if (typeof candidate.detail === 'string' && candidate.detail.trim()) {
    return candidate.detail
  }

  if (typeof candidate.error === 'string' && candidate.error.trim()) {
    return candidate.error
  }

  if (Array.isArray(candidate.detail)) {
    return candidate.detail
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
          return item.msg
        }
        return null
      })
      .filter((item): item is string => Boolean(item))
      .join(', ') || null
  }

  return null
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<unknown>

    if (axiosError.code === 'ECONNABORTED') {
      return new ApiError('Request timed out', {
        code: axiosError.code,
        isTimeoutError: true,
      })
    }

    if (!axiosError.response) {
      return new ApiError('Network request failed', {
        code: axiosError.code,
        isNetworkError: true,
      })
    }

    const status = axiosError.response.status
    const fallbackMessage = `Request failed with status ${status}`
    const responseMessage = extractErrorMessage(axiosError.response.data) ?? fallbackMessage

    return new ApiError(responseMessage, {
      status,
      data: axiosError.response.data,
      code: axiosError.code,
    })
  }

  if (error instanceof Error) {
    return new ApiError(error.message)
  }

  return new ApiError('Unknown API error')
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: false,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => ({
  ...config,
}))

apiClient.interceptors.request.use((config) => {
  Object.assign(config.headers, {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  })

  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(toApiError(error)),
)
