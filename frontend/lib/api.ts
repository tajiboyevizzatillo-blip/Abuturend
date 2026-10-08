export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

// Without a deadline a hung server left every caller suspended forever: the
// exam player's `submitting` flag stayed true, the Next button was disabled
// and the student could only refresh (losing the attempt).
const REQUEST_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  /** HTTP status, or 0 when the request never reached the server. */
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "API error");
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function ensureCsrfToken(): Promise<string | null> {
  const existing = getCsrfToken();
  if (existing) return existing;
  // `cache: "no-store"` matters here: without it the browser may satisfy this
  // from the HTTP cache without re-running the request, so no Set-Cookie
  // arrives, getCsrfToken() keeps returning null, and the subsequent POST goes
  // out with no X-CSRFToken and fails as an opaque 403 "CSRF token missing"
  // that the UI renders as a generic error.
  try {
    await fetch(`${API_BASE}/auth/csrf/`, {
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    // Network failure — fall through and report a missing token.
  }
  return getCsrfToken();
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit & { skipCsrf?: boolean } = {}
): Promise<T> {
  const { skipCsrf, ...init } = options;
  const headers = new Headers(init.headers);

  if (init.body) {
    headers.set("Content-Type", "application/json");
  }

  if (!skipCsrf && init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method)) {
    const token = await ensureCsrfToken();
    if (token) {
      headers.set("X-CSRFToken", token);
    } else {
      // Fail loudly here rather than letting Django answer 403 later: without a
      // token the write cannot succeed, and a clear message is debuggable while
      // "CSRF token missing" is not.
      throw new ApiError(0, "CSRF token could not be obtained; retry the request.");
    }
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  // A caller-supplied signal (navigation aborts) still wins over the timeout.
  if (init.signal) {
    if (init.signal.aborted) controller.abort();
    else init.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...init,
      signal: controller.signal,
      headers,
    });

    if (res.status === 204) {
      return undefined as T;
    }

    let body: unknown = null;
    const text = await res.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }

    if (!res.ok) {
      const detail =
        body && typeof body === "object" && "detail" in body
          ? (body as { detail: unknown }).detail
          : body;
      throw new ApiError(res.status, detail);
    }

    return body as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (timedOut) {
      throw new ApiError(0, "Server javob bermadi (vaqt tugadi). Qayta urinib ko'ring.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  role: "student" | "teacher" | "admin";
  phone: string;
  first_name: string;
  last_name: string;
  date_joined: string;
  is_staff: boolean;
}

export function extractFieldError(
  detail: unknown,
  field?: string
): string | null {
  if (field && typeof detail === "object" && detail !== null) {
    const obj = detail as Record<string, unknown>;
    const value = obj[field];
    if (Array.isArray(value) && value.length > 0) return String(value[0]);
    if (typeof value === "string") return value;
  }
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) return String(detail[0]);
  return null;
}

export async function fetchUser(): Promise<CurrentUser | null> {
  try {
    return await api<CurrentUser>("/auth/me/");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      return null;
    }
    throw e;
  }
}