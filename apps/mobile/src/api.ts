import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import type {
  Filters,
  Listing,
  SearchResult,
  Summary,
  History,
  SavedSearch,
  NotificationInbox,
} from "./types";

export const API_URL =
  process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";
const AUTH_URL = process.env.EXPO_PUBLIC_AUTH_URL || "http://localhost:8001";
let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
export type Account = { id: string; email: string; email_verified: boolean };
type SessionResult = {
  access_token: string;
  refresh_token?: string;
  user: Account;
};
export async function setToken(token: string | null) {
  accessToken = token;
  if (!token) refreshToken = null;
  if (Platform.OS !== "web") {
    if (token) await SecureStore.setItemAsync("realtoruch_token", token);
    else {
      await SecureStore.deleteItemAsync("realtoruch_token");
      await SecureStore.deleteItemAsync("realtoruch_refresh");
    }
  }
}
async function acceptSession(result: SessionResult) {
  await setToken(result.access_token);
  if (Platform.OS !== "web" && result.refresh_token) {
    refreshToken = result.refresh_token;
    await SecureStore.setItemAsync("realtoruch_refresh", refreshToken);
  }
  return result;
}
async function refreshSession() {
  if (refreshing) return refreshing;
  const run = async () => {
    if (Platform.OS !== "web" && !refreshToken) return null;
    const result = await request<SessionResult>(
      "/v1/auth/refresh",
      {
        method: "POST",
        body: JSON.stringify(
          Platform.OS === "web" ? {} : { refresh_token: refreshToken },
        ),
      },
      true,
      false,
    );
    await acceptSession(result);
    return result.access_token;
  };
  // Serialize browser refreshes across tabs: a refresh token is used only once.
  refreshing = (async () =>
    await (Platform.OS === "web" &&
    typeof navigator !== "undefined" &&
    navigator.locks
      ? navigator.locks.request("realtoruch-refresh", run)
      : run()))();
  try {
    return await refreshing;
  } finally {
    refreshing = null;
  }
}
export async function restoreToken() {
  if (Platform.OS !== "web") {
    accessToken = await SecureStore.getItemAsync("realtoruch_token");
    refreshToken = await SecureStore.getItemAsync("realtoruch_refresh");
  }
  try {
    return await refreshSession();
  } catch {
    await setToken(null);
    return null;
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
  authService = false,
  retry = true,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  const usedToken = accessToken;
  try {
    const response = await fetch((authService ? AUTH_URL : API_URL) + path, {
      ...options,
      credentials: authService && Platform.OS === "web" ? "include" : "omit",
      signal: options.signal || controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
    if (response.status === 401 && retry && usedToken) {
      if (accessToken !== usedToken || (await refreshSession()))
        return request<T>(path, options, authService, false);
    }
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((e: { msg: string }) => e.msg).join(". ")
        : data.detail;
      throw new Error(detail || "Something went wrong. Please try again.");
    }
    return data;
  } catch (error) {
    if (
      error instanceof Error &&
      (error.name === "AbortError" || /fetch|network/i.test(error.message))
    )
      throw new Error(
        "Cannot reach the service. Check your connection and try again.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
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
export const api = {
  search: (filters: Filters, page = 1, signal?: AbortSignal) =>
    request<SearchResult>(
      `/v1/listings?${queryString({ ...filters, page, page_size: 24 })}`,
      { signal },
    ),
  detail: (id: string) => request<Listing>(`/v1/listings/${id}`),
  summary: (city: string) =>
    request<Summary>(`/v1/market/summary?${queryString({ city })}`),
  history: (city: string, district = "") =>
    request<History>(`/v1/market/history?${queryString({ city, district })}`),
  favorites: () => request<{ items: Listing[] }>("/v1/me/favorites"),
  favorite: (id: string, saved: boolean) =>
    request(`/v1/me/favorites/${id}`, { method: saved ? "PUT" : "DELETE" }),
  searches: () => request<{ items: SavedSearch[] }>("/v1/me/searches"),
  seen: (id: string) => request(`/v1/me/seen/${id}`, { method: "PUT" }),
  listingState: (ids: string[]) =>
    request<{ seen_ids: string[] }>("/v1/me/listing-state", {
      method: "POST",
      body: JSON.stringify({ listing_ids: ids }),
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
  signIn: async (email: string, password: string, register: boolean) =>
    acceptSession(
      await request<SessionResult>(
        `/v1/auth/${register ? "register" : "login"}`,
        {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            client: Platform.OS === "web" ? "web" : "native",
          }),
        },
        true,
        false,
      ),
    ),
  me: () => request<Account>("/v1/auth/me", {}, true),
  signOut: async () => {
    await request("/v1/auth/logout", { method: "POST" }, true);
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
      },
      true,
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
    const result = await request<{ message: string }>(
      "/v1/auth/account",
      { method: "DELETE", body: JSON.stringify({ password }) },
      true,
    );
    await setToken(null);
    return result;
  },
};
