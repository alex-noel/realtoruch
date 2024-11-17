import { describe, expect, it, vi } from "vitest";
vi.mock("../src/api", () => ({ api: {} }));
import { createAccountCollections } from "../src/hooks/useAccountCollections";
import type { Listing, NotificationInbox, SavedSearch } from "../src/types";

const inbox = (ids: string[], page = 1): NotificationInbox => ({ items: ids.map(id => ({ id } as NotificationInbox["items"][number])), unread_count: ids.length, page, page_size: 30 });
const home = (id: string) => ({ id } as Listing);
const search = (id: string) => ({ id } as SavedSearch);
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
function setup() {
  const loaders = { favorites: vi.fn(async () => [home("one")]), searches: vi.fn(async () => [search("one")]), notifications: vi.fn(async () => inbox(["one"])) };
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
});
