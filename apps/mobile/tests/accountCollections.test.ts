import { describe, expect, it, vi } from "vitest";
vi.mock("../src/api", () => ({ api: {} }));
import { createAccountCollections } from "../src/hooks/useAccountCollections";
import type { Listing, NotificationInbox, SavedSearch } from "../src/types";

const inbox = (ids: string[], page = 1): NotificationInbox => ({ items: ids.map(id => ({ id } as NotificationInbox["items"][number])), unread_count: ids.length, page, page_size: 30, has_more: true, next_cursor: "cursor" });
const home = (id: string) => ({ id } as Listing);
const search = (id: string) => ({ id } as SavedSearch);
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
function setup() {
  const loaders = { favorites: vi.fn(async () => [home("one")]), searches: vi.fn(async () => [search("one")]), notifications: vi.fn(async () => inbox(["one"])), moreNotifications: vi.fn(async (_cursor: string) => inbox([])), readNotification: vi.fn(async (_id: string) => ({})) };
  let state: Parameters<Parameters<typeof createAccountCollections>[1]>[0];
  const controller = createAccountCollections(loaders, next => { state = next; });
  return { loaders, controller, get state() { return state; } };
}
describe("private collection lifecycle", () => {
  it.each(["favorites", "searches", "notifications"] as const)("isolates %s failure and retries without clearing data", async key => {
    const t = setup();
    t.loaders[key].mockRejectedValueOnce(Error("offline"));
    await t.controller.refreshAll();
    expect(t.state[key]).toMatchObject({ loaded: false, loading: false, failed: true });
    for (const other of (["favorites", "searches", "notifications"] as const).filter(k => k !== key)) expect(t.state[other]).toMatchObject({ loaded: true, failed: false });
    await t.controller.refresh(key);
    const previous = t.state[key].data;
    t.loaders[key].mockRejectedValueOnce(Error("offline"));
    await t.controller.refresh(key);
    expect(t.state[key]).toMatchObject({ loaded: true, failed: true, data: previous });
  });
  it("distinguishes loading from a successful empty response", async () => {
    const t = setup(); const pending = deferred<Listing[]>();
    t.loaders.favorites.mockReturnValueOnce(pending.promise);
    const work = t.controller.refresh("favorites");
    expect(t.state.favorites).toMatchObject({ loaded: false, loading: true });
    pending.resolve([]); await work;
    expect(t.state.favorites).toMatchObject({ loaded: true, loading: false, data: [] });
  });
  it("clears immediately and rejects late responses from the previous account", async () => {
    const t = setup(); await t.controller.refreshAll();
    const pending = deferred<Listing[]>(); t.loaders.favorites.mockReturnValueOnce(pending.promise);
    const old = t.controller.refresh("favorites"); t.controller.reset();
    expect(t.state.favorites).toMatchObject({ data: [], loaded: false });
    expect(t.state.searches.data).toEqual([]); expect(t.state.notifications.data.items).toEqual([]);
    await t.controller.refresh("favorites"); pending.resolve([home("old-account")]); await old;
    expect(t.state.favorites.data).toEqual([home("one")]);
  });
  it("keeps the newer response when refreshes finish out of order", async () => {
    const t = setup(); const older = deferred<Listing[]>(); const newer = deferred<Listing[]>();
    t.loaders.favorites.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = t.controller.refresh("favorites"); const second = t.controller.refresh("favorites");
    newer.resolve([home("newer")]); await second;
    older.resolve([home("older")]); await first;
    expect(t.state.favorites.data).toEqual([home("newer")]);
  });
  it("does not let an old read overwrite a successful mutation", async () => {
    const t = setup(); await t.controller.refresh("favorites");
    const pending = deferred<Listing[]>(); t.loaders.favorites.mockReturnValueOnce(pending.promise);
    const old = t.controller.refresh("favorites");
    t.controller.set("favorites", previous => [...previous, home("saved")]);
    pending.resolve([home("one")]); await old;
    expect(t.state.favorites.data).toEqual([home("one"), home("saved")]);
  });
  it("rejects delayed searches and notifications after reset", async () => {
    const t = setup();
    const pendingSearches = deferred<SavedSearch[]>();
    const pendingInbox = deferred<NotificationInbox>();
    t.loaders.searches.mockReturnValueOnce(pendingSearches.promise);
    t.loaders.notifications.mockReturnValueOnce(pendingInbox.promise);
    const oldSearches = t.controller.refresh("searches");
    const oldInbox = t.controller.refresh("notifications");
    t.controller.reset();
    await Promise.all([t.controller.refresh("searches"), t.controller.refresh("notifications")]);
    pendingSearches.resolve([search("old-account")]); pendingInbox.resolve(inbox(["old-account"]));
    await Promise.all([oldSearches, oldInbox]);
    expect(t.state.searches.data).toEqual([search("one")]);
    expect(t.state.notifications.data.items).toEqual([{ id: "one" }]);
  });
  it("keeps older inbox pages and replaces overlapping first-page items", async () => {
    const t = setup(); await t.controller.refresh("notifications");
    t.controller.set("notifications", inbox(["one", "older"], 2));
    t.loaders.notifications.mockResolvedValueOnce(inbox(["new", "one"]));
    await t.controller.refresh("notifications");
    expect(t.state.notifications.data).toMatchObject({ page: 2, items: [{ id: "new" }, { id: "one" }, { id: "older" }] });
  });
  it("adopts a new continuation when the previously loaded inbox was empty", async () => {
    const t = setup();
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox([]), has_more: false, next_cursor: null });
    await t.controller.refresh("notifications");
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox(["new"]), has_more: true, next_cursor: "new-cursor" });
    await t.controller.refresh("notifications");
    expect(t.state.notifications.data).toMatchObject({ has_more: true, next_cursor: "new-cursor" });
  });
  it("preserves the continuation and older rows during a head refresh", async () => {
    const t = setup();
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox(["head"]), next_cursor: "head-cursor" });
    await t.controller.refresh("notifications");
    t.loaders.moreNotifications.mockResolvedValueOnce({ ...inbox(["tail"], 2), next_cursor: "tail-cursor" });
    await t.controller.moreNotifications();
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox(["new", "head"]), next_cursor: "new-head-cursor" });
    await t.controller.refresh("notifications");
    expect(t.state.notifications.data).toMatchObject({ next_cursor: "tail-cursor", has_more: true, items: [{ id: "new" }, { id: "head" }, { id: "tail" }] });
  });
  it("fills a multi-page burst after an exhausted head and sorts retained rows", async () => {
    const t = setup();
    const row = (id: string, date: string) => ({ id, created_at: date, read_at: null } as NotificationInbox["items"][number]);
    const old = row("old", "2026-01-01T00:00:00");
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox([]), items: [old], has_more: false, next_cursor: null });
    await t.controller.refresh("notifications");
    const burst = Array.from({ length: 40 }, (_, index) => row(String(index).padStart(2, "0"), "2026-02-01T00:00:00"));
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox([]), items: burst.slice(0, 30), has_more: true, next_cursor: "gap" });
    await t.controller.refresh("notifications");
    expect(t.state.notifications.data).toMatchObject({ has_more: true, next_cursor: "gap" });
    t.loaders.moreNotifications.mockResolvedValueOnce({ ...inbox([]), items: [...burst.slice(30), old], has_more: false, next_cursor: null });
    await t.controller.moreNotifications();
    expect(t.state.notifications.data.items.map(item => item.id)).toEqual([...burst.map(item => item.id), "old"]);
    expect(t.state.notifications.data.has_more).toBe(false);
  });
  it("keeps a restarted cursor if an older page completes after a disconnected head", async () => {
    const t = setup(); await t.controller.refresh("notifications");
    const oldPage = deferred<NotificationInbox>(); t.loaders.moreNotifications.mockReturnValueOnce(oldPage.promise);
    const pending = t.controller.moreNotifications();
    t.loaders.notifications.mockResolvedValueOnce({ ...inbox(["new"]), next_cursor: "gap" });
    await t.controller.refresh("notifications");
    oldPage.resolve({ ...inbox(["tail"]), next_cursor: "old-tail" }); await pending;
    expect(t.state.notifications.data).toMatchObject({ next_cursor: "gap", has_more: true });
    expect(t.state.notifications.data.items.map(item => item.id)).toEqual(["new", "one", "tail"]);
  });
  it("guards duplicate load-more and retains its cursor on failure for retry", async () => {
    const t = setup(); await t.controller.refresh("notifications");
    const pending = deferred<NotificationInbox>(); t.loaders.moreNotifications.mockReturnValueOnce(pending.promise);
    const first = t.controller.moreNotifications(); await t.controller.moreNotifications();
    expect(t.loaders.moreNotifications).toHaveBeenCalledTimes(1);
    pending.resolve({ ...inbox(["tail"]), has_more: true, next_cursor: "next" }); await first;
    t.loaders.moreNotifications.mockRejectedValueOnce(Error("offline"));
    await t.controller.moreNotifications();
    expect(t.state.inboxActivity.moreFailed).toBe(true);
    expect(t.state.notifications.data).toMatchObject({ next_cursor: "next", items: [{ id: "one" }, { id: "tail" }] });
    t.loaders.moreNotifications.mockResolvedValueOnce({ ...inbox(["last"]), has_more: false, next_cursor: null });
    await t.controller.moreNotifications();
    expect(t.loaders.moreNotifications).toHaveBeenLastCalledWith("next");
    expect(t.state.notifications.data).toMatchObject({ has_more: false, next_cursor: null, items: [{ id: "one" }, { id: "tail" }, { id: "last" }] });
  });
  it("keeps unread rows on failure and fences old head responses after a successful read", async () => {
    const t = setup();
    t.loaders.notifications.mockResolvedValueOnce(inbox(["one", "two"])); await t.controller.refresh("notifications");
    t.loaders.readNotification.mockRejectedValueOnce(Error("offline")); await t.controller.readNotification("one");
    expect(t.state.inboxActivity.readFailed).toContain("one");
    expect(t.state.notifications.data.items[0].read_at).toBeUndefined();
    const pendingHead = deferred<NotificationInbox>(); t.loaders.notifications.mockReturnValueOnce(pendingHead.promise);
    const head = t.controller.refresh("notifications");
    const read = deferred<{}>(); t.loaders.readNotification.mockReturnValueOnce(read.promise);
    const first = t.controller.readNotification("one"); await t.controller.readNotification("one");
    expect(t.loaders.readNotification).toHaveBeenCalledTimes(2);
    read.resolve({}); await first; pendingHead.resolve(inbox(["one", "two"])); await head;
    expect(t.state.notifications.data.items[0].read_at).toBeTruthy();
    expect(t.state.notifications.data.items[1].read_at).toBeUndefined();
    expect(t.state.notifications.data.unread_count).toBe(1);
  });
  it("drops pending page and read results when the account resets", async () => {
    const t = setup(); await t.controller.refresh("notifications");
    const page = deferred<NotificationInbox>(), read = deferred<{}>();
    t.loaders.moreNotifications.mockReturnValueOnce(page.promise); t.loaders.readNotification.mockReturnValueOnce(read.promise);
    const more = t.controller.moreNotifications(), marking = t.controller.readNotification("one");
    t.controller.reset(); await t.controller.refresh("notifications");
    page.resolve(inbox(["old-private"])); read.resolve({}); await Promise.all([more, marking]);
    expect(t.state.notifications.data.items).toEqual([{ id: "one" }]);
    expect(t.state.inboxActivity).toEqual({ more: false, moreFailed: false, reading: [], readFailed: [] });
  });

});
