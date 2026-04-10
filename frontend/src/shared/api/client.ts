export class ApiError extends Error {
  status: number;
  errorCode?: string;
  details?: unknown;

  constructor(message: string, status: number, errorCode?: string, details?: unknown) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

// 所有请求统一从环境变量读取后端地址，便于本地开发和部署切换。
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const data = response.status === 204 ? null : await response.json().catch(() => null);

  // 统一解析后端的 detail/error_code，避免每个页面单独处理错误结构。
  if (!response.ok) {
    throw new ApiError(
      data?.detail ?? "请求失败，请稍后重试",
      response.status,
      data?.error_code,
      data?.errors,
    );
  }

  return data as T;
}
