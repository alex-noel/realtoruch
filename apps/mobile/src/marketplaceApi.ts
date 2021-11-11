import { request } from "./api";
import { Listing } from "./types";
export type Profile = {
  id: string;
  name: string;
  kind: "private" | "agency";
  description: string;
};
export type Draft = {
  title: string;
  description: string;
  city: string;
  district: string;
  region: string;
  address: string;
  lat: number;
  lon: number;
  area_m2: number;
  rooms: number;
  floor: number | null;
  rent_pln: number;
  fees_pln: number | null;
  deposit_pln: number | null;
  commission_pln: number | null;
  property_type: "apartment" | "house" | "room";
  amenities: string[];
  images: string[];
};
export type Advert = {
  id: string;
  hidden?: boolean;
  listing_id: string | null;
  state: string;
  version: number;
  advert: Draft;
};
export type Conversation = {
  id: string;
  title: string;
  listing_id: string | null;
  updated_at: string;
  unread_count: number;
  blocked: boolean;
  can_unblock: boolean;
};
export type ConversationPage = {
  items: Conversation[];
  next_cursor: string | null;
};
export type Message = {
  id: string;
  body: string;
  mine: boolean;
  created_at: string;
};
export type Thread = {
  id: string;
  items: Message[];
  next_cursor: string | null;
  blocked: boolean;
  can_unblock: boolean;
};
export type Report = {
  id: string;
  reason: string;
  hidden: boolean;
  listing: Listing;
};
const write = (method: string, data: unknown) => ({
  method,
  body: JSON.stringify(data),
});
// The shared request timeout is bypassed by a caller signal. Preserve the
// request deadline for cancellable inbox calls until the shared client composes
// its own signals.
async function messageRequest<T>(
  path: string,
  signal?: AbortSignal,
  options?: RequestInit,
) {
  if (!signal) return request<T>(path, options);
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal.aborted) cancel();
  else signal.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(cancel, 12000);
  try {
    return await request<T>(path, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", cancel);
  }
}
export const market = {
  profile: () => request<{ profile: Profile | null }>("/v1/me/advertiser"),
  saveProfile: (profile: Omit<Profile, "id">) =>
    request<{ profile: Profile }>("/v1/me/advertiser", write("PUT", profile)),
  advertiser: (id: string, signal?: AbortSignal) =>
    messageRequest<{ profile: Profile; items: Listing[] }>(
      `/v1/advertisers/${id}`,
      signal,
    ),
  adverts: () => request<{ items: Advert[] }>("/v1/me/adverts"),
  saveAdvert: (draft: Draft, existing?: Advert) =>
    existing
      ? request<Advert>(
          `/v1/me/adverts/${existing.id}`,
          write("PUT", { version: existing.version, advert: draft }),
        )
      : request<Advert>("/v1/me/adverts", write("POST", draft)),
  publish: (advert: Advert) =>
    request<Advert>(
      `/v1/me/adverts/${advert.id}/publish`,
      write("POST", { version: advert.version }),
    ),
  withdraw: (advert: Advert) =>
    request<Advert>(
      `/v1/me/adverts/${advert.id}/withdraw`,
      write("POST", { version: advert.version }),
    ),
  appeal: (advert: Advert, reason: string) =>
    request<{ message: string }>(
      `/v1/me/adverts/${advert.id}/appeal`,
      write("POST", { action: "restore", reason }),
    ),
  publicAdvert: (id: string) =>
    request<{ listing_id: string }>(`/v1/adverts/${id}`),
  conversations: (cursor?: string, signal?: AbortSignal) =>
    messageRequest<ConversationPage>(
      `/v1/me/conversations${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
      signal,
    ),
  thread: (id: string, before?: string, signal?: AbortSignal) =>
    messageRequest<Thread>(
      `/v1/me/conversations/${id}${before ? `?before=${encodeURIComponent(before)}` : ""}`,
      signal,
    ),
  start: (
    advert: string,
    body: string,
    client_id: string,
    signal?: AbortSignal,
  ) =>
    messageRequest<{ id: string }>(
      `/v1/adverts/${advert}/conversations`,
      signal,
      write("POST", { body, client_id }),
    ),
  reply: (id: string, body: string, client_id: string, signal?: AbortSignal) =>
    messageRequest<Message>(
      `/v1/me/conversations/${id}/messages`,
      signal,
      write("POST", { body, client_id }),
    ),
  read: (id: string, last_message_id: string, signal?: AbortSignal) =>
    messageRequest<{ read: true }>(
      `/v1/me/conversations/${id}/read`,
      signal,
      write("PUT", { last_message_id }),
    ),
  block: (id: string, blocked: boolean, signal?: AbortSignal) =>
    messageRequest<{ blocked: boolean }>(
      `/v1/me/conversations/${id}/block`,
      signal,
      write("PUT", { blocked }),
    ),
  identity: (id: string) =>
    request<{
      sources: {
        id: string;
        name: string;
        title: string;
        address: string;
        rent_pln: number;
        url: string;
      }[];
      candidates: Listing[];
    }>(`/v1/moderation/listings/${id}/identity`),
  merge: (id: string, target_id: string, reason: string) =>
    request(
      `/v1/moderation/listings/${id}/merge`,
      write("POST", { target_id, reason }),
    ),
  split: (id: string, source_id: string, reason: string) =>
    request(
      `/v1/moderation/listings/${id}/split`,
      write("POST", { source_id, reason }),
    ),
  capabilities: () => request<{ moderator: boolean }>("/v1/me/capabilities"),
  reports: () => request<{ items: Report[] }>("/v1/moderation/reports"),
  review: (
    id: string,
    action: "hide" | "restore" | "dismiss",
    reason: string,
  ) =>
    request(
      `/v1/moderation/reports/${id}/review`,
      write("POST", { action, reason }),
    ),
};
