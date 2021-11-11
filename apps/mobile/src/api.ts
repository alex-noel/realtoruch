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
export async function setToken(token: string | null) {
  accessToken = token;
  // Browser tokens remain in memory. Mobile uses the platform's secure key store.
  if (Platform.OS !== "web") {
    if (token) await SecureStore.setItemAsync("realtoruch_token", token);
    else await SecureStore.deleteItemAsync("realtoruch_token");
  }
}
export async function restoreToken() {
  if (Platform.OS !== "web")
    accessToken = await SecureStore.getItemAsync("realtoruch_token");
  return accessToken;
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
  authService = false,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch((authService ? AUTH_URL : API_URL) + path, {
      ...options,
      signal: options.signal || controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
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
  signIn: (email: string, password: string, register: boolean) =>
    request<{ access_token: string; user: { email: string } }>(
      `/v1/auth/${register ? "register" : "login"}`,
      { method: "POST", body: JSON.stringify({ email, password }) },
      true,
    ),
  me: () => request<{ email: string }>("/v1/auth/me", {}, true),
};
