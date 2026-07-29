import { resolveApiPath, type ApiResponse } from "../contracts/knowledgeApi";

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
  const requestInit: RequestInit = {
    headers: { Accept: "application/json" },
  };

  if (signal && acceptsAbortSignal(requestUrl, signal)) {
    requestInit.signal = signal;
  }

  const response = await fetch(requestUrl, requestInit);

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
