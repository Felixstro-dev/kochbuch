const BASE = '/api/v1';

import { showToast } from '#lib/toast.svelte';
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function csrfToken(): string {
  if (typeof document === 'undefined') return '';
  const match = document.cookie.match(/(?:^|;\s*)kochbuch_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function buildQuery(params?: Record<string, string | number | boolean | null | undefined | string[]>): string {
  if (!params) return '';
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(','));
    } else {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

interface RequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | null | undefined | string[]>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { query, headers, ...rest } = options;
  const method = (rest.method || 'GET').toUpperCase();
  const finalHeaders = new Headers(headers);
  if (!(rest.body instanceof FormData) && rest.body !== undefined) {
    finalHeaders.set('Content-Type', 'application/json');
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = csrfToken();
    if (token) finalHeaders.set('X-CSRF-Token', token);
  }
  finalHeaders.set('Accept', 'application/json');

  const response = await fetch(`${BASE}${path}${buildQuery(query)}`, {
    ...rest,
    method,
    headers: finalHeaders,
    credentials: 'same-origin'
  });

  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : typeof body === 'string' && body
          ? body
          : `Anfrage fehlgeschlagen (${response.status}).`;
    showToast(detail, 'error');
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
  url: (path: string, query?: Record<string, string | number | boolean | null | undefined | string[]>) =>
    `${BASE}${path}${buildQuery(query)}`
};
