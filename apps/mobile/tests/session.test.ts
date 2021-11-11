import { beforeEach, describe, expect, it, vi } from "vitest";

const f = vi.hoisted(() => ({ platform: { OS: "ios" }, store: new Map<string, string>(), failRead: false, failWrite: false, failDelete: false, writeGate: null as Promise<void> | null, enteredWrite: false }));
vi.mock("react-native", () => ({ Platform: f.platform }));
vi.mock("expo-secure-store", () => ({
  getItemAsync: async (key: string) => { if (f.failRead) throw Error("storage"); return f.store.get(key) ?? null; },
  setItemAsync: async (key: string, value: string) => { if (f.failWrite) throw Error("storage"); if (f.writeGate) { f.enteredWrite = true; await f.writeGate; } f.store.set(key, value); },
  deleteItemAsync: async (key: string) => { if (f.failDelete) throw Error("storage"); f.store.delete(key); },
}));
const result = (access: string, refresh = "rotated") => ({ access_token: access, refresh_token: refresh, user: { id: "1", email: "x@example.test", email_verified: true } });
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
async function load() { return import("../src/api"); }
beforeEach(() => { vi.resetModules(); f.platform.OS = "ios"; f.store.clear(); f.failRead = false; f.failWrite = false; f.failDelete = false; f.writeGate = null; f.enteredWrite = false; vi.unstubAllGlobals(); });

describe("session resilience", () => {
  it("cannot restore credentials from a refresh completing after confirmed logout", async () => {
    f.store.set("realtoruch_refresh", "original");
    let release!: (value: Response) => void;
    const pending = new Promise<Response>(resolve => { release = resolve; });
    let refreshes = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/refresh")) return ++refreshes === 1 ? response(result("old", "original")) : pending;
      return response({ signed_out: true });
    }));
    const client = await load();
    const states: string[] = [];
    client.subscribeSession(state => states.push(state));
    await client.restoreToken();
    const late = client.restoreToken();
    await vi.waitFor(() => expect(refreshes).toBe(2));
    await client.api.signOut();
    release(response(result("late", "late-refresh")));
    await late.catch(() => null);
    expect(f.store.has("realtoruch_refresh")).toBe(false);
    expect(f.store.has("realtoruch_token")).toBe(false);
    expect(states.at(-1)).toBe("signed-out");
  });

  it("never replays an old account mutation under a newly signed-in account", async () => {
    let release!: (value: Response) => void;
    const delayed = new Promise<Response>(resolve => { release = resolve; });
    let logins = 0;
    const mutationTokens: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("/login")) return response(result(++logins === 1 ? "account-a" : "account-b"));
      const token = (options.headers as Record<string, string>).Authorization;
      if (url.includes("/favorites/")) {
        mutationTokens.push(token);
        return mutationTokens.length === 1 ? delayed : response({ saved: true });
      }
      return response({ token });
    }));
    const client = await load();
    await client.api.signIn("a@example.test", "synthetic-password", false);
    const mutation = client.request("/v1/me/favorites/home", { method: "PUT" });
    await client.api.signIn("b@example.test", "synthetic-password", false);
    release(response({}, 401));
    await expect(mutation).rejects.toBeInstanceOf(Error);
    expect(mutationTokens).toEqual(["Bearer account-a"]);
    expect(await client.request("/probe")).toEqual({ token: "Bearer account-b" });
  });

  it("fences an in-progress secure write behind confirmed logout cleanup", async () => {
    f.store.set("realtoruch_refresh", "original");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/refresh") ? response(result("new", "new-refresh")) : response({ signed_out: true })));
    const client = await load(); await client.setToken("old");
    let release!: () => void; f.writeGate = new Promise<void>(resolve => { release = resolve; });
    const restore = client.restoreToken();
    await vi.waitFor(() => expect(f.enteredWrite).toBe(true));
    const logout = client.api.signOut();
    await vi.waitFor(() => expect(client.getSessionState()).toBe("signed-out"));
    release(); await logout; await expect(restore).rejects.toMatchObject({ kind: "superseded" });
    expect(f.store.size).toBe(0); expect(client.getSessionState()).toBe("signed-out");
  });
  it("reports local cleanup failure after confirmed logout and blocks same-instance restore", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ signed_out: true })));
    const client = await load(); await client.setToken("old"); f.store.set("realtoruch_refresh", "revoked"); f.failDelete = true;
    await client.api.signOut(); expect(client.getSessionState()).toBe("storage-cleanup");
    expect(await client.restoreToken()).toBe(null); expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
    expect(client.getSessionState()).toBe("storage-cleanup");
  });
  it("publishes signed out for an empty native store", async () => {
    const client = await load(); const states: string[] = []; client.subscribeSession(s => states.push(s));
    expect(await client.restoreToken()).toBe(null); expect(states.at(-1)).toBe("signed-out");
  });
  it("serializes web refresh before a newer login changes the cookie", async () => {
    f.platform.OS = "web"; let tail = Promise.resolve(); let cookie = "old";
    const locks = { request: (_name: string, run: () => Promise<unknown>) => {
      const next = tail.then(run); tail = next.then(() => undefined, () => undefined); return next;
    } };
    vi.stubGlobal("navigator", { locks }); let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
    let started = false; const order: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/refresh")) { started = true; await gate; cookie = "rotated-old"; order.push("refresh"); return response(result("old")); }
      cookie = "new-account"; order.push("login"); return response(result("new"));
    }));
    const client = await load(); const refresh = client.restoreToken();
    await vi.waitFor(() => expect(started).toBe(true));
    const login = client.api.signIn("new@example.test", "synthetic-password", false);
    release(); await expect(refresh).rejects.toMatchObject({ kind: "superseded" }); await login;
    expect(order).toEqual(["refresh", "login"]); expect(cookie).toBe("new-account");
  });
  it("serializes web refresh before logout deletes the cookie", async () => {
    f.platform.OS = "web"; let tail = Promise.resolve(); let cookie = "old";
    const locks = { request: (_name: string, run: () => Promise<unknown>) => { const next = tail.then(run); tail = next.then(() => undefined, () => undefined); return next; } };
    vi.stubGlobal("navigator", { locks }); let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; }); let started = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/refresh")) { started = true; await gate; cookie = "rotated"; return response(result("new")); }
      cookie = ""; return response({ signed_out: true });
    }));
    const client = await load(); await client.setToken("old"); const refresh = client.restoreToken();
    await vi.waitFor(() => expect(started).toBe(true)); const logout = client.api.signOut(); release();
    await refresh; await logout; expect(cookie).toBe(""); expect(client.getSessionState()).toBe("signed-out");
  });
  it("does not deadlock logout refresh when another refresh is queued for the web lock", async () => {
    f.platform.OS = "web"; let release!: () => void; let locked!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    const entered = new Promise<void>(resolve => { locked = resolve; });
    let tail = Promise.resolve();
    const locks = { request: (_name: string, run: () => Promise<unknown>) => { const next = tail.then(run); tail = next.then(() => undefined, () => undefined); return next; } };
    vi.stubGlobal("navigator", { locks }); const blocker = locks.request("realtoruch-refresh", async () => { locked(); await gate; }); await entered;
    let logoutCount = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/refresh") ? response(result("new")) : response({ signed_out: true }, ++logoutCount === 1 ? 401 : 200)));
    const client = await load(); await client.setToken("old");
    const logout = client.api.signOut(); const queued = client.restoreToken();
    release(); await blocker; await logout; await expect(queued).rejects.toMatchObject({ kind: "superseded" });
    expect(logoutCount).toBe(2); expect(client.getSessionState()).toBe("signed-out");
  });
  it("finishes account deletion cookie cleanup before a newer login", async () => {
    f.platform.OS = "web";
    let tail = Promise.resolve(); let cookie = "old"; let started = false;
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    const locks = { request: (_name: string, run: () => Promise<unknown>) => {
      const next = tail.then(run); tail = next.then(() => undefined, () => undefined); return next;
    } };
    vi.stubGlobal("navigator", { locks });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/account")) { started = true; await gate; cookie = ""; return response({ message: "Deleted" }); }
      cookie = "new-account"; return response(result("new-account"));
    }));
    const client = await load(); await client.setToken("old-account");
    const deletion = client.api.deleteAccount("synthetic-password");
    await vi.waitFor(() => expect(started).toBe(true));
    const login = client.api.signIn("new@example.test", "synthetic-password", false);
    release();
    await expect(deletion).rejects.toMatchObject({ kind: "superseded" });
    await login;
    expect(cookie).toBe("new-account");
    expect(client.isCurrentAccessToken("new-account")).toBe(true);
  });
  it("replaces an old in-progress secure write only after it finishes", async () => {
    f.store.set("realtoruch_refresh", "original");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/refresh") ? response(result("old-rotation", "old-refresh")) : response(result("account-b", "refresh-b"))));
    const client = await load(); let release!: () => void;
    f.writeGate = new Promise<void>(resolve => { release = resolve; });
    const old = client.restoreToken(); await vi.waitFor(() => expect(f.enteredWrite).toBe(true));
    const login = client.api.signIn("b@example.test", "synthetic-password", false);
    f.writeGate = null; release(); await expect(old).rejects.toMatchObject({ kind: "superseded" }); await login;
    expect(f.store.get("realtoruch_refresh")).toBe("refresh-b"); expect(f.store.get("realtoruch_token")).toBe("account-b");
  });
  it("returns bounded validation feedback without echoing server-provided secrets", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response({ detail: [{ loc: ["body", "email"], msg: "secret" }] }, 422)).mockResolvedValueOnce(response({ detail: "secret" }, 400)));
    const client = await load(); await expect(client.request("/test", {}, false, false)).rejects.toThrow("Please check: email.");
    await expect(client.request("/test", {}, false, false)).rejects.toThrow("Request could not be completed. Please check your details.");
  });
  it("preserves native refresh on 503 and restores on retry", async () => {
    f.store.set("realtoruch_refresh", "original");
    const fetch = vi.fn().mockResolvedValueOnce(response({}, 503)).mockResolvedValueOnce(response(result("new")));
    vi.stubGlobal("fetch", fetch);
    const client = await load(); const states: string[] = []; client.subscribeSession(s => states.push(s));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "transient" });
    expect(f.store.get("realtoruch_refresh")).toBe("original"); expect(states.at(-1)).toBe("offline");
    await expect(client.restoreToken()).resolves.toBe("new"); expect(f.store.get("realtoruch_refresh")).toBe("rotated");
  });
  it("coalesces ten 401s and retries all with the rotated access token", async () => {
    let release!: (v: Response) => void;
    const gate = new Promise<Response>(resolve => { release = resolve; });
    const fetch = vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("/refresh")) return gate;
      const token = (options.headers as Record<string, string>).Authorization;
      return token === "Bearer old" ? response({}, 401) : response({ token });
    });
    vi.stubGlobal("fetch", fetch); const client = await load();
    f.store.set("realtoruch_refresh", "original"); await client.setToken("old");
    // Load the refresh material once without consuming it on the network.
    f.failRead = false;
    const initial = client.restoreToken(); release(response(result("old", "original"))); await initial;
    let releaseRefresh!: (v: Response) => void;
    const refreshGate = new Promise<Response>(resolve => { releaseRefresh = resolve; });
    fetch.mockImplementation(async (url: string, options: RequestInit) => url.endsWith("/refresh") ? refreshGate : (options.headers as Record<string, string>).Authorization === "Bearer old" ? response({}, 401) : response({ token: (options.headers as Record<string, string>).Authorization }));
    fetch.mockClear(); const requests = Array.from({ length: 10 }, () => client.request<{token: string}>("/private"));
    await vi.waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith("/refresh"))).toHaveLength(1));
    releaseRefresh(response(result("new"))); const values = await Promise.all(requests);
    expect(values.map(v => v.token)).toEqual(Array(10).fill("Bearer new"));
    expect(fetch.mock.calls.filter(([url]) => url.endsWith("/refresh"))).toHaveLength(1);
  });
  it("requires reauthentication after a lost consumed response is rejected", async () => {
    f.store.set("realtoruch_refresh", "original");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(Error("network")).mockResolvedValueOnce(response({}, 401)));
    const client = await load(); const states: string[] = []; client.subscribeSession(s => states.push(s));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "transient" });
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "invalid" });
    expect(states.at(-1)).toBe("reauth"); expect(f.store.has("realtoruch_refresh")).toBe(false);
  });
  it("keeps logout retry visible on outage, then clears on invalid session", async () => {
    const fetch = vi.fn().mockRejectedValueOnce(Error("offline")).mockResolvedValueOnce(response({}, 401)).mockResolvedValueOnce(response({}, 401));
    vi.stubGlobal("fetch", fetch); const client = await load(); await client.setToken("old");
    const states: string[] = []; client.subscribeSession(s => states.push(s));
    await expect(client.api.signOut()).rejects.toThrow("Could not confirm"); expect(states.at(-1)).toBe("logout-retry");
    await client.api.signOut(); expect(states.at(-1)).toBe("signed-out"); expect(f.store.has("realtoruch_token")).toBe(false);
  });
  it("serializes two web instances using a shared cookie under Web Locks", async () => {
    f.platform.OS = "web";
    let tail = Promise.resolve(); let active = 0; let peak = 0; let cookie = 0;
    const locks = { request: (_name: string, run: () => Promise<string | null>) => {
      const next = tail.then(async () => { active++; peak = Math.max(peak, active); try { return await run(); } finally { active--; } });
      tail = next.then(() => undefined, () => undefined); return next;
    } };
    vi.stubGlobal("navigator", { locks });
    const fetch = vi.fn(async (_url: string, options: RequestInit) => {
      expect(options.credentials).toBe("include"); expect(JSON.parse(options.body as string)).toEqual({});
      const used = cookie; await Promise.resolve(); cookie = used + 1;
      return response(result(`access${cookie}`));
    });
    vi.stubGlobal("fetch", fetch); const one = await load(); vi.resetModules(); const two = await load();
    expect(await Promise.all([one.restoreToken(), two.restoreToken()])).toEqual(["access1", "access2"]);
    expect(peak).toBe(1); expect(cookie).toBe(2); expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("does not refresh web without locks", async () => {
    f.platform.OS = "web"; const fetch = vi.fn(); vi.stubGlobal("fetch", fetch); vi.stubGlobal("navigator", {});
    const client = await load(); await client.setToken("known-access");
    const states: string[] = []; client.subscribeSession(s => states.push(s));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "invalid" }); expect(fetch).not.toHaveBeenCalled(); expect(states.at(-1)).toBe("reauth");
  });
  it("keeps a fresh anonymous web visit and its in-flight public request signed out", async () => {
    f.platform.OS = "web";
    vi.stubGlobal("navigator", { locks: { request: (_name: string, run: () => Promise<unknown>) => run() } });
    let release!: (value: Response) => void;
    const pending = new Promise<Response>(resolve => { release = resolve; });
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/refresh") ? response({}, 401) : pending));
    const client = await load();
    const listingRequest = client.request("/v1/listings");
    await expect(client.restoreToken()).resolves.toBe(null);
    release(response({ items: [] }));
    await expect(listingRequest).resolves.toEqual({ items: [] });
    expect(client.getSessionState()).toBe("signed-out");
  });
  it("preserves storage on read failure and requires sign in after rotated token write failure", async () => {
    f.store.set("realtoruch_refresh", "original"); f.failRead = true;
    const client = await load(); await expect(client.restoreToken()).rejects.toMatchObject({ kind: "storage" }); expect(f.store.get("realtoruch_refresh")).toBe("original");
    f.failRead = false; f.failWrite = true; vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(result("new"))));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "storage" }); expect(f.store.has("realtoruch_refresh")).toBe(false);
  });
});
