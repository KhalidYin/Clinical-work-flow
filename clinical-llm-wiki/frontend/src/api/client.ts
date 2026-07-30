import { resolveApiPath, type ApiResponse } from "../contracts/knowledgeApi";

export const LOCAL_BEARER_STORAGE_KEY = "knowledgeLedgerBearerToken";

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<ApiResponse<T>> {
  const requestUrl = resolveApiPath(path);
  const headers: Record<string, string> = { Accept: "application/json" };
  const bearerToken = window.sessionStorage.getItem(LOCAL_BEARER_STORAGE_KEY);
  if (bearerToken) {
    headers.Authorization = `Bearer ${bearerToken}`;
  }
  const requestInit: RequestInit = { headers };

  if (signal && acceptsAbortSignal(requestUrl, signal)) {
    requestInit.signal = signal;
  }

  const response = await fetch(requestUrl, requestInit);

  if (!response.ok) {
    throw new ApiRequestError(`请求失败（HTTP ${response.status}）`, response.status);
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

async function requestJson<T>(path: string, init: RequestInit): Promise<ApiResponse<T>> {
  const requestUrl = resolveApiPath(path);
  const headers = new Headers(init.headers);
  const bearerToken = window.sessionStorage.getItem(LOCAL_BEARER_STORAGE_KEY);
  if (bearerToken) {
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }
  const response = await fetch(requestUrl, { ...init, headers });
  if (!response.ok) {
    throw new ApiRequestError(`请求失败（HTTP ${response.status}）`, response.status);
  }
  return (await response.json()) as ApiResponse<T>;
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
