/**
 * Server-only backend bridge for Next.js Route Handlers.
 *
 * Security Rules (Prompt 00 / 00A / Person 3 Handoff):
 * - NEVER use NEXT_PUBLIC_* for backend tokens, service keys, or wallet private keys.
 * - Read-only endpoints require no token.
 * - Operator control endpoints (`/api/agent/start`, `/api/agent/stop`, `/api/demo/scenario`)
 *   require BOTH:
 *     1. Server-side `AEGIS_CONTROL_TOKEN` configured in Next.js server env
 *     2. Caller-supplied `X-AEGIS-Admin-Secret` matching `AEGIS_DASHBOARD_ADMIN_SECRET`
 *        (prevents creating an unauthenticated frontend proxy to private operator controls;
 *         keeps public judge access strictly view-only with zero trade privileges).
 */

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export function getBackendBaseUrl(): string {
  const raw = process.env.AEGIS_BACKEND_URL || DEFAULT_BACKEND_URL;
  return raw.replace(/\/+$/, "");
}

export function isAdminAuthorized(request: Request): {
  authorized: boolean;
  reason?: string;
  statusCode: number;
} {
  const backendToken = process.env.AEGIS_CONTROL_TOKEN;
  const dashboardAdminSecret = process.env.AEGIS_DASHBOARD_ADMIN_SECRET;

  if (!backendToken || !dashboardAdminSecret) {
    return {
      authorized: false,
      statusCode: 503,
      reason:
        "View-Only Judge Mode active: operator control credentials are not configured on this server.",
    };
  }

  const providedSecret = request.headers.get("x-aegis-admin-secret") || "";
  if (!providedSecret || providedSecret !== dashboardAdminSecret) {
    return {
      authorized: false,
      statusCode: 401,
      reason:
        "Unauthorized: valid X-AEGIS-Admin-Secret header required for operator control mutations.",
    };
  }

  return { authorized: true, statusCode: 200 };
}

export async function fetchBackendJson<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number }
): Promise<{ ok: boolean; status: number; data: T | null; error?: string }> {
  const baseUrl = getBackendBaseUrl();
  const timeoutMs = init?.timeoutMs ?? 6000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await response.text();
    let parsed: T | null = null;
    try {
      parsed = text ? (JSON.parse(text) as T) : null;
    } catch {
      parsed = null;
    }
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        data: parsed,
        error: text || `HTTP ${response.status}`,
      };
    }
    return { ok: true, status: response.status, data: parsed };
  } catch (err) {
    return {
      ok: false,
      status: 503,
      data: null,
      error: err instanceof Error ? err.message : "Backend unreachable",
    };
  } finally {
    clearTimeout(timer);
  }
}
