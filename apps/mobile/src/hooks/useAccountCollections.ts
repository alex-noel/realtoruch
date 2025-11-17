import { useState } from "react";
import { api } from "../api";
import type { Listing, NotificationInbox, SavedSearch } from "../types";

type Data = { favorites: Listing[]; searches: SavedSearch[]; notifications: NotificationInbox };
type Key = keyof Data;
export type Collection<T> = { data: T; loaded: boolean; loading: boolean; failed: boolean };
type State = { [K in Key]: Collection<Data[K]> } & { inboxActivity: { more: boolean; moreFailed: boolean; reading: string[]; readFailed: string[] } };
const initial = (): State => ({
  favorites: { data: [], loaded: false, loading: false, failed: false },
  searches: { data: [], loaded: false, loading: false, failed: false },
  inboxActivity: { more: false, moreFailed: false, reading: [], readFailed: [] },
  notifications: { data: { items: [], unread_count: 0, page: 1, page_size: 30, has_more: false, next_cursor: null }, loaded: false, loading: false, failed: false },
});

// Merge by identity and restore the same order used by the server. A locally
// confirmed read is monotonic even if an older page is still in flight.
function mergeInbox(incoming: NotificationInbox["items"], previous: NotificationInbox["items"]) {
  const old = new Map(previous.map(item => [item.id, item]));
  const merged = incoming.map(item => ({ ...item, read_at: item.read_at || old.get(item.id)?.read_at || item.read_at }));
  const ids = new Set(incoming.map(item => item.id));
  merged.push(...previous.filter(item => !ids.has(item.id)));
  return merged.sort((a, b) => {
    if (!a.created_at || !b.created_at) return 0;
    if (a.created_at !== b.created_at) return a.created_at > b.created_at ? -1 : 1;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}
type Loaders = { [K in Key]: () => Promise<Data[K]> } & { moreNotifications: (cursor: string) => Promise<NotificationInbox>; readNotification: (id: string) => Promise<unknown> };
export function createAccountCollections(loaders: Loaders, changed: (state: State) => void) {
  let state = initial();
  let epoch = 0;
  const sequence: Record<Key, number> = { favorites: 0, searches: 0, notifications: 0 };
  function update<K extends Key>(key: K, value: Collection<Data[K]>) { state = { ...state, [key]: value }; changed(state); }
  function reset() { epoch++; state = initial(); changed(state); }
  function activity(next: State["inboxActivity"]) { state = { ...state, inboxActivity: next }; changed(state); }
  async function refresh<K extends Key>(key: K) {
    const requestEpoch = epoch, requestSequence = ++sequence[key];
    update(key, { ...(state[key] as Collection<Data[K]>), loading: true });
    try {
      let data = await (loaders[key] as () => Promise<Data[K]>)();
      if (epoch !== requestEpoch || sequence[key] !== requestSequence) return;
      if (key === "notifications") {
        const incoming = data as NotificationInbox, previous = state.notifications.data;
        const previousIds = new Set(previous.items.map(item => item.id));
        // A full, disconnected head means more than one page arrived since the
        // last refresh. Traverse from the new head to fill the gap; otherwise
        // keep the existing tail continuation and all already loaded rows.
        const disconnected = state.notifications.loaded && previous.items.length > 0 && incoming.has_more &&
          !incoming.items.some(item => previousIds.has(item.id));
        const continuation = state.notifications.loaded && previous.items.length && !disconnected
          ? { page: previous.page, has_more: previous.has_more, next_cursor: previous.next_cursor } : {};
        data = { ...incoming, ...continuation, items: mergeInbox(incoming.items, previous.items) } as Data[K];
      }
      update(key, { data, loaded: true, loading: false, failed: false });
    } catch {
      if (epoch === requestEpoch && sequence[key] === requestSequence) update(key, { ...(state[key] as Collection<Data[K]>), loading: false, failed: true });
    }
  }
  function set<K extends Key>(key: K, action: Data[K] | ((previous: Data[K]) => Data[K])) {
    sequence[key]++;
    const previous = state[key] as Collection<Data[K]>;
    const data = typeof action === "function" ? (action as (previous: Data[K]) => Data[K])(previous.data) : action;
    update(key, { ...previous, data, loading: false });
  }
  async function moreNotifications() {
    const { data, loaded } = state.notifications;
    if (!loaded || state.inboxActivity.more || !data.has_more || !data.next_cursor) return;
    const requestEpoch = epoch, cursor = data.next_cursor;
    activity({ ...state.inboxActivity, more: true, moreFailed: false });
    try {
      const next = await loaders.moreNotifications(cursor);
      if (epoch !== requestEpoch) return;
      // A head refresh may have completed while this page was in flight.
      // Keep its current rows, updating only the continuation and new tail.
      const previous = state.notifications;
      // A disconnected head refresh can restart traversal during this request.
      // Its newer cursor wins; the old response may still contribute rows.
      const sameCursor = previous.data.next_cursor === cursor;
      update("notifications", { ...previous, data: { ...previous.data,
        ...(sameCursor ? { page: previous.data.page + 1, has_more: next.has_more, next_cursor: next.next_cursor } : {}),
        items: mergeInbox(previous.data.items, next.items) } });
      activity({ ...state.inboxActivity, more: false, moreFailed: false });
    } catch {
      if (epoch === requestEpoch) activity({ ...state.inboxActivity, more: false, moreFailed: true });
    }
  }
  async function readNotification(id: string) {
    if (state.inboxActivity.reading.includes(id)) return;
    const requestEpoch = epoch;
    activity({ ...state.inboxActivity, reading: [...state.inboxActivity.reading, id], readFailed: state.inboxActivity.readFailed.filter(item => item !== id) });
    try {
      await loaders.readNotification(id);
      if (epoch !== requestEpoch) return;
      // Invalidate older head responses before locally marking just this row.
      set("notifications", previous => {
        const unread = previous.items.some(item => item.id === id && !item.read_at);
        return { ...previous, unread_count: Math.max(0, previous.unread_count - (unread ? 1 : 0)),
          items: previous.items.map(item => item.id === id && !item.read_at ? { ...item, read_at: new Date().toISOString() } : item) };
      });
      activity({ ...state.inboxActivity, reading: state.inboxActivity.reading.filter(item => item !== id) });
    } catch {
      if (epoch === requestEpoch) activity({ ...state.inboxActivity, reading: state.inboxActivity.reading.filter(item => item !== id), readFailed: [...state.inboxActivity.readFailed, id] });
    }
  }
  return { reset, refresh, moreNotifications, readNotification, refreshAll: () => Promise.all([refresh("favorites"), refresh("searches"), refresh("notifications")]), set };
}
export function useAccountCollections() {
  const [state, setState] = useState<State>(initial);
  const [controller] = useState(() => createAccountCollections({
    favorites: async () => (await api.favorites()).items,
    searches: async () => (await api.searches()).items,
    notifications: () => api.notifications(),
    moreNotifications: cursor => api.notifications(cursor),
    readNotification: id => api.readNotification(id),
  }, setState));
  return { state, ...controller };
}
