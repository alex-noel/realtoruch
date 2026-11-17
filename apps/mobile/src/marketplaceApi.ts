import { request, requestBlob } from "./api";
import { Listing, MediaAsset, MediaMime } from "./types";
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
  media_ids?: string[];
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
function messageRequest<T>(
  path: string,
  signal?: AbortSignal,
  options?: RequestInit,
) {
  return request<T>(path, signal ? { ...options, signal } : options);
}
const mediaPath = (id: string) => `/v1/me/media/${encodeURIComponent(id)}`;
const mediaKeyPath = (key: string) => `/v1/me/media/by-key/${encodeURIComponent(key)}`;
export function makeOwnerMedia(transport: NonNullable<Parameters<typeof requestBlob>[1]>["transport"]) {
  return {
    upload: (key: string, body: Blob, mime: MediaMime, signal: AbortSignal) => request<MediaAsset>("/v1/me/media", { method: "POST", headers: { "Content-Type": mime, "Idempotency-Key": key }, body, signal, transport, timeoutMs: 60_000, redirect: "error" }),
    status: (id: string, signal: AbortSignal) => request<MediaAsset>(mediaPath(id), { signal }),
    statusByKey: (key: string, signal: AbortSignal) => request<MediaAsset>(mediaKeyPath(key), { signal }),
    cancel: (key: string, signal: AbortSignal) => request<MediaAsset>(mediaKeyPath(key), { method: "DELETE", signal }),
    remove: (id: string, signal: AbortSignal) => request<MediaAsset>(mediaPath(id), { method: "DELETE", signal }),
    describe: (id: string, description: string, signal: AbortSignal) => request<MediaAsset>(mediaPath(id), { ...write("PATCH", { description }), signal }),
    preview: (id: string, size: "display" | "thumbnail", signal: AbortSignal) => requestBlob(`${mediaPath(id)}/${size}`, { signal, transport, redirect: "error", cache: "no-store" }),
  };
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
    request<{ listing_id: string }>(`/v1/adverts/${id}`, { anonymous: true }),
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
