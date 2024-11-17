import { useState } from "react";
import { api } from "../api";
import type { Listing, NotificationInbox, SavedSearch } from "../types";

type Data = { favorites: Listing[]; searches: SavedSearch[]; notifications: NotificationInbox };
type Key = keyof Data;
export type Collection<T> = { data: T; loaded: boolean; loading: boolean; failed: boolean };
type State = { [K in Key]: Collection<Data[K]> };
const initial = (): State => ({
  favorites: { data: [], loaded: false, loading: false, failed: false },
  searches: { data: [], loaded: false, loading: false, failed: false },
  notifications: { data: { items: [], unread_count: 0, page: 1, page_size: 30 }, loaded: false, loading: false, failed: false },
});
type Loaders = { [K in Key]: () => Promise<Data[K]> };
export function createAccountCollections(loaders: Loaders, changed: (state: State) => void) {
  let state = initial();
  let epoch = 0;
  const sequence: Record<Key, number> = { favorites: 0, searches: 0, notifications: 0 };
  function update<K extends Key>(key: K, value: Collection<Data[K]>) { state = { ...state, [key]: value }; changed(state); }
  function reset() { epoch++; state = initial(); changed(state); }
  async function refresh<K extends Key>(key: K) {
    const requestEpoch = epoch, requestSequence = ++sequence[key];
    update(key, { ...state[key], loading: true });
    try {
      let data = await loaders[key]();
      if (epoch !== requestEpoch || sequence[key] !== requestSequence) return;
      if (key === "notifications") {
        const incoming = data as NotificationInbox, previous = state.notifications.data;
        data = { ...incoming, page: previous.page, items: [...incoming.items, ...previous.items.filter(item => !incoming.items.some(newer => newer.id === item.id))] } as Data[K];
      }
      update(key, { data, loaded: true, loading: false, failed: false });
    } catch {
      if (epoch === requestEpoch && sequence[key] === requestSequence) update(key, { ...state[key], loading: false, failed: true });
    }
  }
  function set<K extends Key>(key: K, action: Data[K] | ((previous: Data[K]) => Data[K])) {
    sequence[key]++;
    const previous = state[key];
    const data = typeof action === "function" ? (action as (previous: Data[K]) => Data[K])(previous.data) : action;
    update(key, { ...previous, data, loading: false });
  }
  return { reset, refresh, refreshAll: () => Promise.all([refresh("favorites"), refresh("searches"), refresh("notifications")]), set };
}
export function useAccountCollections() {
  const [state, setState] = useState<State>(initial);
  const [controller] = useState(() => createAccountCollections({
    favorites: async () => (await api.favorites()).items,
    searches: async () => (await api.searches()).items,
    notifications: () => api.notifications(),
  }, setState));
  return { state, ...controller };
}
