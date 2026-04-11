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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

function isFormData(body: unknown): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const formDataBody = isFormData(body);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: formDataBody
      ? headers
      : {
          "Content-Type": "application/json",
          ...headers,
        },
    body: body === undefined ? undefined : formDataBody ? body : JSON.stringify(body),
  });

  const data = response.status === 204 ? null : await response.json().catch(() => null);

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
