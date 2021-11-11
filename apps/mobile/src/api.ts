import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import type {
  Filters,
  Listing,
  SearchResult,
  Summary,
  Sources,
  History,
  SavedSearch,
  NotificationInbox,
} from "./types";

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_URL = process.env.EXPO_PUBLIC_AUTH_URL || "http://localhost:8001";
let accessToken: string | null = null;
let refreshToken: string | null = null;
let accountId: string | null = null;
let generation = 0;
let refreshing: { generation: number; promise: Promise<string | null> } | null = null;
let storageQueue: Promise<void> = Promise.resolve();
let storageBlocked = false;
export type SessionState = "signed-out" | "active" | "offline" | "reauth" | "logout-retry" | "storage-cleanup";
let sessionState: SessionState = "signed-out";
const listeners = new Set<(state: SessionState) => void>();
export function subscribeSession(listener: (state: SessionState) => void) {
  listeners.add(listener); listener(sessionState);
  return () => { listeners.delete(listener); };
}
function publish(state: SessionState) { sessionState = state; listeners.forEach(listener => listener(state)); }
export function getSessionState() { return sessionState; }
export function isCurrentAccessToken(token: string) { return accessToken === token; }
export class SessionError extends Error {
  constructor(public kind: "invalid" | "forbidden" | "transient" | "http" | "storage" | "superseded", message: string, public status?: number) {
    super(message); this.name = "SessionError";
  }
}
export type Account = { id: string; email: string; email_verified: boolean };
type SessionResult = { access_token: string; refresh_token?: string; user: Account };
function checkIntent(expected: number) {
  if (expected !== generation) throw new SessionError("superseded", "The account session changed.");
}
function storage<T>(action: () => Promise<T>): Promise<T> {
  const result = storageQueue.then(action);
  storageQueue = result.then(() => undefined, () => undefined);
  return result;
}
async function clearStorage() {
  if (Platform.OS !== "web") await storage(async () => {
    // Attempt both deletions even if one fails.
    const outcomes = await Promise.allSettled([
      SecureStore.deleteItemAsync("realtoruch_token"), SecureStore.deleteItemAsync("realtoruch_refresh"),
    ]);
    if (outcomes.some(outcome => outcome.status === "rejected")) throw new Error("storage cleanup");
  });
}
function clearMemory(state: SessionState) {
  generation++; accessToken = null; refreshToken = null; accountId = null; publish(state);
  return generation;
}
export async function setToken(token: string | null) {
  if (!token) {
    const intent = clearMemory("signed-out");
    try { await clearStorage(); storageBlocked = false; } catch { storageBlocked = true; if (intent === generation) publish("storage-cleanup"); }
    return;
  }
  const intent = generation;
  await storage(async () => {
    checkIntent(intent);
    if (Platform.OS !== "web") await SecureStore.setItemAsync("realtoruch_token", token);
    checkIntent(intent); accessToken = token;
  });
}
async function invalidate(expected: number) {
  checkIntent(expected);
  const intent = clearMemory("reauth");
  try { await clearStorage(); storageBlocked = false; } catch { storageBlocked = true; }
  checkIntent(intent);
}
async function acceptSession(result: SessionResult, intent: number) {
  try {
    await storage(async () => {
      checkIntent(intent);
      if (Platform.OS !== "web") {
        if (result.refresh_token) await SecureStore.setItemAsync("realtoruch_refresh", result.refresh_token);
        checkIntent(intent);
        await SecureStore.setItemAsync("realtoruch_token", result.access_token);
        checkIntent(intent);
      }
      refreshToken = result.refresh_token ?? null;
      accessToken = result.access_token;
      accountId = result.user.id;
    });
    checkIntent(intent);
  } catch (error) {
    checkIntent(intent);
    await invalidate(intent);
    throw new SessionError("storage", "Secure storage is unavailable. Sign in again.");
  }
  storageBlocked = false;
  publish("active");
  return result;
}
async function refreshSession(intent = generation, lockHeld = false) {
  checkIntent(intent);
  const anonymousBootstrap = Platform.OS === "web" && !accessToken && sessionState === "signed-out";
  if (!lockHeld && refreshing?.generation === intent) return refreshing.promise;
  const run = async () => {
    checkIntent(intent);
    if (Platform.OS !== "web" && !refreshToken) return null;
    const result = await request<SessionResult>("/v1/auth/refresh", {
      method: "POST", body: JSON.stringify(Platform.OS === "web" ? {} : { refresh_token: refreshToken }),
    }, true, false);
    checkIntent(intent);
    if (accountId !== null && result.user.id !== accountId) {
      throw new SessionError("invalid", "The account changed in another tab. Sign in again.");
    }
    await acceptSession(result, intent);
    return result.access_token;
  };
  const promise = (async () => {
    try {
      if (Platform.OS === "web") {
        if (typeof navigator === "undefined" || !navigator.locks) throw new SessionError("invalid", "Sign in again. This browser cannot safely restore a session across tabs.");
        return lockHeld ? await run() : await navigator.locks.request("realtoruch-refresh", run);
      }
      return await run();
    } catch (error) {
      if (error instanceof SessionError && error.kind === "storage" && generation === intent + 1 && sessionState === "reauth") throw error;
      checkIntent(intent);
      if (anonymousBootstrap && error instanceof SessionError && error.kind === "invalid") {
        // A first visit has no readable HttpOnly-cookie state. A missing or
        // revoked cookie simply means signed out; public requests stay valid.
        publish("signed-out");
        return null;
      }
      if (error instanceof SessionError && (error.kind === "invalid" || error.kind === "forbidden")) await invalidate(intent);
      else if (!(error instanceof SessionError && error.kind === "storage")) publish("offline");
      throw error;
    }
  })();
  refreshing = { generation: intent, promise };
  try { return await promise; } finally { if (refreshing?.promise === promise) refreshing = null; }
}
export async function restoreToken() {
  const intent = generation;
  if (storageBlocked) { publish("storage-cleanup"); return null; }
  if (Platform.OS !== "web") {
    try {
      const values = await storage(async () => {
        checkIntent(intent);
        const access = await SecureStore.getItemAsync("realtoruch_token");
        const refresh = await SecureStore.getItemAsync("realtoruch_refresh");
        checkIntent(intent); return { access, refresh };
      });
      checkIntent(intent); accessToken = values.access; refreshToken = values.refresh;
      if (!refreshToken) { accessToken = null; publish("signed-out"); return null; }
    } catch (error) {
      checkIntent(intent); publish("offline");
      throw new SessionError("storage", "Secure storage is unavailable. Try again.");
    }
  }
  return refreshSession(intent);
}
// Validation details are allowlisted; never echo arbitrary server text, credentials or input values.
function validationMessage(data: unknown): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") {
    const safe = ["Invalid email or password", "Password is incorrect", "Email already registered", "Incorrect password", "Invalid credentials", "Email or password is incorrect"];
    if (safe.includes(detail)) return detail + ".";
  }
  if (Array.isArray(detail)) {
    const fields = detail.map(item => Array.isArray(item?.loc) ? item.loc.at(-1) : null).filter(field => ["email", "password", "name"].includes(field));
    if (fields.length) return `Please check: ${[...new Set(fields)].join(", ")}.`;
  }
  return "Request could not be completed. Please check your details.";
}
function linkValidationMessage(path: string, status: number, data: unknown) {
  if (status !== 400 && status !== 401 && status !== 403) return null;
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (path === "/v1/auth/verify-email" || path === "/v1/auth/reset-password") {
    return detail === "This link has already been used"
      ? "This link has already been used."
      : "This link is invalid or has expired.";
  }
  if (path === "/v1/notifications/email/confirm") {
    return "This confirmation link expired or was already used.";
  }
  if (path === "/v1/notifications/email/unsubscribe") {
    return "This unsubscribe link is unavailable.";
  }
  return null;
}
function cancelled() {
  const error = new Error("Request cancelled.");
  error.name = "AbortError";
  return error;
}

// A caller can stop waiting without cancelling the session refresh shared by
// other requests or interrupting rotation under the cross-tab lock.
function waitForRefresh(refresh: Promise<string | null>, signal: AbortSignal) {
  return new Promise<string | null>((resolve, reject) => {
    const cleanup = () => signal.removeEventListener("abort", abort);
    const abort = () => {
      cleanup();
      reject(cancelled());
    };
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
    void refresh.then(
      (token) => { cleanup(); resolve(token); },
      (error) => { cleanup(); reject(error); },
    );
  });
}

export async function request<T>(path: string, options: RequestInit & { anonymous?: boolean } = {}, authService = false, retry = true, retried = false, lockHeld = false): Promise<T> {
  const { signal: callerSignal, anonymous, ...init } = options;
  const controller = new AbortController();
  const abort = () => controller.abort();
  callerSignal?.addEventListener("abort", abort, { once: true });
  if (callerSignal?.aborted) abort();
  const timeout = setTimeout(abort, 12000);
  const intent = generation;
  function checkResponse() {
    if (controller.signal.aborted) throw cancelled();
    if (!anonymous) checkIntent(intent);
  }
  async function send(mayRetry: boolean, didRetry: boolean): Promise<T> {
    checkResponse();
    const usedToken = anonymous ? null : accessToken;
    const response = await fetch((authService ? AUTH_URL : API_URL) + path, {
      ...init, credentials: authService && Platform.OS === "web" ? "include" : "omit",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(usedToken ? { Authorization: `Bearer ${usedToken}` } : {}), ...init.headers },
    });
    checkResponse();
    if (response.status === 401 && mayRetry && usedToken && path !== "/v1/auth/refresh") {
      if (accessToken !== usedToken) return send(false, true);
      const refresh = refreshSession(intent, lockHeld);
      // Logout holds the cookie lock until any rotation it started settles.
      const token = lockHeld ? await refresh : await waitForRefresh(refresh, controller.signal);
      checkResponse();
      if (token) return send(false, true);
    }
    if (!response.ok) {
      const kind = response.status === 401 ? "invalid" : response.status === 403 ? "forbidden" : response.status >= 500 ? "transient" : "http";
      let data: unknown; try { data = await response.json(); } catch { data = null; }
      checkResponse();
      if (kind === "invalid" && usedToken && (mayRetry || didRetry) && path !== "/v1/auth/refresh") await invalidate(intent);
      const linkMessage = linkValidationMessage(path, response.status, data);
      throw new SessionError(kind, linkMessage ?? (kind === "invalid" ? ((path.endsWith("/login") || path.endsWith("/account")) ? validationMessage(data) : "Session expired or revoked. Sign in again.") : kind === "transient" ? "Cannot reach the service. Try again." : validationMessage(data)), response.status);
    }
    const data = await response.json();
    checkResponse();
    return data;
  }
  try {
    return await send(retry, retried);
  } catch (error) {
    if (callerSignal?.aborted) throw cancelled();
    if (error instanceof SessionError) throw error;
    if (!anonymous) checkIntent(intent);
    throw new SessionError("transient", "Cannot reach the service. Check your connection and try again.");
  } finally {
    clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abort);
  }
}
export function queryString(values: object) {
  return Object.entries(values)
    .filter(
      ([, value]) => value !== undefined && value !== null && value !== "",
    )
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`,
    )
    .join("&");
}
async function withAuthCookieLock<T>(run: (lockHeld: boolean) => Promise<T>): Promise<T> {
  if (Platform.OS === "web" && typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request("realtoruch-refresh", () => run(true));
  }
  return run(false);
}
export const api = {
  search: (filters: Filters, page = 1, signal?: AbortSignal) =>
    request<SearchResult>(
      `/v1/listings?${queryString({ ...filters, page, page_size: 24 })}`,
      { signal, anonymous: true },
    ),
  detail: (id: string) =>
    request<Listing>(`/v1/listings/${id}`, { anonymous: true }),
  summary: (city: string, signal?: AbortSignal) =>
    request<Summary>(`/v1/market/summary?${queryString({ city })}`, { signal, anonymous: true }),
  sources: (city: string, signal?: AbortSignal) =>
    request<Sources>(`/v1/sources?${queryString({ city })}`, { signal, anonymous: true }),
  history: (city: string, district = "") =>
    request<History>(`/v1/market/history?${queryString({ city, district })}`),
  favorites: () => request<{ items: Listing[] }>("/v1/me/favorites"),
  favorite: (id: string, saved: boolean) =>
    request(`/v1/me/favorites/${id}`, { method: saved ? "PUT" : "DELETE" }),
  searches: () => request<{ items: SavedSearch[] }>("/v1/me/searches"),
  seen: (id: string, signal?: AbortSignal) => request(`/v1/me/seen/${id}`, { method: "PUT", signal }),
  listingState: (ids: string[], signal?: AbortSignal) =>
    request<{ seen_ids: string[] }>("/v1/me/listing-state", {
      method: "POST",
      body: JSON.stringify({ listing_ids: ids }),
      signal,
    }),
  notifications: (page = 1) =>
    request<NotificationInbox>(`/v1/me/notifications?page=${page}`),
  readNotification: (id: string) =>
    request(`/v1/me/notifications/${id}/read`, { method: "PUT" }),
  saveSearch: (name: string, filters: Filters) =>
    request("/v1/me/searches", {
      method: "POST",
      body: JSON.stringify({ name, filters }),
    }),
  deleteSearch: (id: string) =>
    request(`/v1/me/searches/${id}`, { method: "DELETE" }),
  report: (id: string, reason: string) =>
    request(`/v1/listings/${id}/reports`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  signIn: async (email: string, password: string, register: boolean) => {
    const intent = clearMemory("signed-out");
    try { await clearStorage(); storageBlocked = false; } catch { storageBlocked = true; }
    checkIntent(intent);
    return withAuthCookieLock(async () => {
      checkIntent(intent);
      const result = await request<SessionResult>(`/v1/auth/${register ? "register" : "login"}`, {
        method: "POST", body: JSON.stringify({ email, password, client: Platform.OS === "web" ? "web" : "native" }),
      }, true, false);
      checkIntent(intent);
      return acceptSession(result, intent);
    });
  },
  me: () => request<Account>("/v1/auth/me", {}, true),
  signOut: async () => {
    const intent = generation;
    try {
      await withAuthCookieLock(async lockHeld => {
        checkIntent(intent);
        await request("/v1/auth/logout", { method: "POST" }, true, true, false, lockHeld);
        checkIntent(intent);
        await setToken(null);
      });
      return;
    } catch (error) {
      if (error instanceof SessionError && error.kind === "superseded") throw error;
      // A refresh 401 invalidates and advances the intent; the session is already gone.
      if (error instanceof SessionError && error.kind === "invalid" && generation !== intent) {
        if (generation === intent + 1 && sessionState === "reauth") publish(storageBlocked ? "storage-cleanup" : "signed-out");
        return;
      }
      checkIntent(intent);
      if (!(error instanceof SessionError && error.kind === "invalid")) {
        publish("logout-retry");
        throw new SessionError("transient", "Could not confirm sign out. Check your connection and try again.");
      }
    }
    checkIntent(intent);
    await setToken(null);
  },
  resetRequest: (email: string) =>
    request<{ message: string }>(
      "/v1/auth/request-password-reset",
      {
        method: "POST",
        body: JSON.stringify({ email }),
      },
      true,
      false,
    ),
  resetPassword: (token: string, password: string) =>
    request<{ message: string }>(
      "/v1/auth/reset-password",
      {
        method: "POST",
        body: JSON.stringify({ token, password }),
      },
      true,
      false,
    ),
  verifyAccount: (token: string) =>
    request<{ message: string }>(
      "/v1/auth/verify-email",
      {
        method: "POST",
        body: JSON.stringify({ token }),
        anonymous: true,
      },
      true,
      false,
    ),
  emailAlertLink: (action: "confirm-email" | "unsubscribe-email", token: string) =>
    request<{ message: string }>(
      `/v1/notifications/email/${action === "confirm-email" ? "confirm" : "unsubscribe"}`,
      { method: "POST", body: JSON.stringify({ token }), anonymous: true },
      false,
      false,
    ),
  requestVerification: () =>
    request<{ message: string }>(
      "/v1/auth/request-verification",
      { method: "POST" },
      true,
    ),
  sessions: () =>
    request<{
      items: {
        id: string;
        label: string;
        current: boolean;
        last_used_at: string;
      }[];
    }>("/v1/auth/sessions", {}, true),
  revokeSession: (id: string) =>
    request(`/v1/auth/sessions/${id}`, { method: "DELETE" }, true),
  deleteAccount: async (password: string) => {
    const intent = generation;
    return withAuthCookieLock(async () => {
      checkIntent(intent);
      const result = await request<{ message: string }>(
        "/v1/auth/account",
        { method: "DELETE", body: JSON.stringify({ password }) },
        true,
        false,
      );
      checkIntent(intent);
      await setToken(null);
      return result;
    });
  },
};
