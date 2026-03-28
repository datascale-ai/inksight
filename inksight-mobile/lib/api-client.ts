const DEFAULT_API_BASE = 'http://127.0.0.1:8080/api';
const API_BASE_ENV_KEYS = [
  'EXPO_PUBLIC_INKSIGHT_API_BASE',
  'EXPO_PUBLIC_INKSIGHT_BACKEND_API_BASE',
] as const;

type ApiFetchOptions = {
  method?: string;
  token?: string | null;
  body?: BodyInit | ArrayBuffer | Record<string, unknown> | null;
  contentType?: string | null;
  headers?: Record<string, string>;
};

function stripTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function ensureApiSuffix(value: string) {
  const normalized = stripTrailingSlash(value.trim());
  if (!normalized) {
    return '';
  }
  if (/\/api$/i.test(normalized)) {
    return normalized;
  }
  return `${normalized}/api`;
}

function resolveApiBase() {
  for (const key of API_BASE_ENV_KEYS) {
    const value = process.env[key];
    if (typeof value === 'string' && value.trim()) {
      return ensureApiSuffix(value);
    }
  }
  return stripTrailingSlash(DEFAULT_API_BASE);
}

/** Expo Web 走浏览器 fetch，会受 CORS 限制，需在后端配置 INKSIGHT_CORS_ALLOW_LAN 或 INKSIGHT_CORS_ORIGINS；原生无此限制。 */
export function buildApiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const base = resolveApiBase();
  // 后端常返回以 /api/ 开头的相对路径；若 API base 已以 /api 结尾，避免拼成 .../api/api/preview
  if (/\/api$/i.test(base) && /^\/api(\/|\?|$)/i.test(normalizedPath)) {
    const stripped = normalizedPath.replace(/^\/api/i, '');
    const suffix = stripped.startsWith('/') || stripped.startsWith('?') ? stripped : `/${stripped}`;
    return `${base}${suffix}`;
  }
  return `${base}${normalizedPath}`;
}

export function buildAuthHeaders(token?: string | null, contentType: string | null = 'application/json') {
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  return headers;
}

function normalizeBody(body: ApiFetchOptions['body'], contentType: string | null | undefined) {
  if (body == null) {
    return undefined;
  }
  if (body instanceof ArrayBuffer) {
    return body;
  }
  if (typeof body === 'string') {
    return body;
  }
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return body;
  }
  if (contentType === 'application/json' || contentType == null) {
    return JSON.stringify(body);
  }
  return body as BodyInit;
}

const DEFAULT_FETCH_TIMEOUT_MS = 30_000;

/** RN / 部分 Hermes 环境没有 AbortSignal.timeout，用 AbortController 兼容。 */
function withTimeoutSignal(ms: number): { signal: AbortSignal; clear: () => void } {
  if (typeof AbortSignal !== 'undefined' && typeof (AbortSignal as { timeout?: (n: number) => AbortSignal }).timeout === 'function') {
    return { signal: AbortSignal.timeout(ms), clear: () => {} };
  }
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return {
    signal: controller.signal,
    clear: () => clearTimeout(id),
  };
}

export async function apiFetch(path: string, options: ApiFetchOptions = {}) {
  const {
    method = 'GET',
    token,
    body,
    contentType = 'application/json',
    headers = {},
  } = options;
  const requestHeaders: Record<string, string> = {
    ...buildAuthHeaders(token, contentType),
    ...headers,
  };

  const { signal, clear } = withTimeoutSignal(DEFAULT_FETCH_TIMEOUT_MS);
  try {
    return await fetch(buildApiUrl(path), {
      method,
      headers: requestHeaders,
      body: normalizeBody(body, contentType),
      signal,
    });
  } finally {
    clear();
  }
}

export async function apiRequest<T>(path: string, options: ApiFetchOptions = {}) {
  const response = await apiFetch(path, options);
  const responseType = response.headers.get('content-type') || '';
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`.trim();
    try {
      if (responseType.includes('application/json')) {
        const payload = (await response.json()) as { error?: string; detail?: string; message?: string };
        message = payload.error || payload.detail || payload.message || message;
      } else {
        const text = await response.text();
        if (text) {
          message = text;
        }
      }
    } catch {
      // Keep the fallback message.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null as T;
  }
  if (responseType.includes('application/json')) {
    return (await response.json()) as T;
  }
  return (await response.text()) as T;
}
