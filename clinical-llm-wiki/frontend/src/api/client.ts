import {
  resolveApiPath,
  type ApiErrorCode,
  type ApiResponse,
  type ErrorResponse,
} from "../contracts/knowledgeApi";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | null;

  constructor(message: string, status: number, code: ApiErrorCode | null = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<ApiResponse<T>> {
  const requestUrl = resolveApiPath(path);
  const headers: Record<string, string> = { Accept: "application/json" };
  const requestInit: RequestInit = { headers, credentials: "same-origin" };

  if (signal && acceptsAbortSignal(requestUrl, signal)) {
    requestInit.signal = signal;
  }

  const response = await fetch(requestUrl, requestInit);

  if (!response.ok) {
    throw await apiError(response);
  }

  return (await response.json()) as ApiResponse<T>;
}

export async function postMultipart<T>(
  path: string,
  body: FormData,
  idempotencyKey: string,
): Promise<ApiResponse<T>> {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body,
  });
}

export async function postAction<T>(path: string): Promise<ApiResponse<T>> {
  return requestJson<T>(path, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
}

export async function postNoContent(path: string): Promise<void> {
  const requestUrl = resolveApiPath(path);
  const response = await fetch(requestUrl, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRF-Protection": "1",
    },
  });
  if (!response.ok) {
    throw await apiError(response);
  }
}

export async function postJson<T, TBody extends object>(
  path: string,
  body: TBody,
): Promise<ApiResponse<T>> {
  return requestJson<T>(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

async function requestJson<T>(path: string, init: RequestInit): Promise<ApiResponse<T>> {
  const requestUrl = resolveApiPath(path);
  const headers = new Headers(init.headers);
  headers.set("X-CSRF-Protection", "1");
  const response = await fetch(requestUrl, {
    ...init,
    credentials: "same-origin",
    headers,
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as ApiResponse<T>;
}

async function apiError(response: Response): Promise<ApiRequestError> {
  try {
    const payload = (await response.clone().json()) as Partial<ErrorResponse>;
    const code = payload.error?.code ?? null;
    const message = payload.error?.message ?? `请求失败（HTTP ${response.status}）`;
    return new ApiRequestError(message, response.status, code);
  } catch {
    return new ApiRequestError(`请求失败（HTTP ${response.status}）`, response.status);
  }
}

function acceptsAbortSignal(url: string, signal: AbortSignal): boolean {
  try {
    new Request(url, { signal });
    return true;
  } catch {
    // jsdom and Node fetch can expose AbortSignal objects from different realms.
    return false;
  }
}
