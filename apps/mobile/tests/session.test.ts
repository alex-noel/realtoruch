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

describe("business error recovery", () => {
  it.each([
    ["/v1/me/adverts/a", 409, "This advert changed on another device. Reload before editing.", "version_conflict"],
    ["/v1/me/adverts/a/publish", 403, "Verify your account email first in Account", "verification_required"],
    ["/v1/me/conversations/a/messages", 429, "Please wait before sending more messages", "rate_limited"],
    ["/v1/me/searches", 422, "You can save up to 30 searches", "search_limit"],
    ["/v1/me/adverts", 422, "Create your advertiser profile first", "profile_required"],
    ["/v1/me/adverts", 422, "You can keep up to 100 adverts", "advert_limit"],
    ["/v1/me/advertiser", 409, "Withdraw published adverts before changing advertiser type", "profile_type_conflict"],
    ["/v1/me/conversations/a/messages", 403, "This conversation is blocked", "conversation_blocked"],
    ["/v1/me/conversations/a/messages", 409, "Client message ID already used with different text", "message_retry_conflict"],
    ["/v1/me/adverts/a/appeal", 409, "A review is already pending", "appeal_pending"],
    ["/v1/moderation/reports/a/review", 409, "Report is no longer pending", "already_reviewed"],
    ["/v1/me/adverts/a/publish", 409, "This home is hidden after review. Submit an appeal to request another review.", "moderation_hidden"],
  ])("maps %s %s without invalidating the account", async (path, status, detail, code) => {
    const fetch = vi.fn().mockResolvedValueOnce(response(result("valid-session"))).mockResolvedValueOnce(response({ detail }, Number(status)));
    vi.stubGlobal("fetch", fetch);
    const client = await load();
    await client.api.signIn("synthetic@example.test", "synthetic-password", false);
    await expect(client.request(String(path))).rejects.toMatchObject({ code, status, fields: [] });
    expect(client.getSessionState()).toBe("active");
    expect(client.isCurrentAccessToken("valid-session")).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["/unrelated", 409, "This advert changed on another device. Reload before editing."],
    ["/unrelated", 409, "Invalid credentials"],
    ["/unrelated", 409, [{ loc: ["body", "email"], msg: "private-input" }]],
    ["/v1/me/adverts/a", 422, "This advert changed on another device. Reload before editing."],
    ["/v1/me/adverts/a", 409, "<script>secret-token</script>"],
    ["/v1/me/adverts/a", 409, { token: "secret-token", message: "owner@example.test" }],
  ])("does not trust an unknown route/status/detail combination", async (path, status, detail) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail }, Number(status))));
    const client = await load();
    await expect(client.request(String(path))).rejects.toMatchObject({ code: "unknown", message: "Request could not be completed. Please check your details.", fields: [] });
  });

  it("maps only known owner validation fields, including image-array errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: [
      { loc: ["body", "advert", "rent_pln"], msg: "secret-input", input: "secret-input" },
      { loc: ["body", "advert", "images", 2], msg: "https://private.invalid/secret" },
      { loc: ["body", "secret-token"], msg: "owner@example.test" },
      { loc: ["body", "advert", "rent_pln"] },
      null,
    ] }, 422)));
    const client = await load();
    await expect(client.request("/v1/me/adverts/a")).rejects.toMatchObject({ code: "validation", fields: ["rent_pln", "images"], message: "Please check: rent_pln, images." });
  });
});

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

  it("does not replay a mutation when another tab changed the cookie account", async () => {
    f.platform.OS = "web";
    vi.stubGlobal("navigator", { locks: { request: (_name: string, run: () => Promise<unknown>) => run() } });
    const mutationTokens: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("/login")) return response({ ...result("account-a"), user: { ...result("a").user, id: "a" } });
      if (url.endsWith("/refresh")) return response({ ...result("account-b"), user: { ...result("b").user, id: "b" } });
      mutationTokens.push((options.headers as Record<string, string>).Authorization);
      return response({}, 401);
    }));
    const client = await load();
    await client.api.signIn("a@example.test", "synthetic-password", false);
    await expect(client.api.favorite("home-a", true)).rejects.toMatchObject({ kind: "invalid" });
    expect(mutationTokens).toEqual(["Bearer account-a"]);
    expect(client.getSessionState()).toBe("reauth");
    expect(client.isCurrentAccessToken("account-b")).toBe(false);
  });

  it("fences an in-progress secure write behind confirmed logout cleanup", async () => {
    f.store.set("realtoruch_refresh", "original");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/refresh") ? response(result("new", "new-refresh")) : response({ signed_out: true })));
    const client = await load(); await client.setToken("old");
    let release!: () => void; f.writeGate = new Promise<void>(resolve => { release = resolve; });
    const restore = client.restoreToken();
    await vi.waitFor(() => expect(f.enteredWrite).toBe(true));
    // setToken alone leaves sessionState initially signed-out. Observe the new
    // logout publication, rather than accidentally accepting that initial state.
    let confirmed!: () => void;
    const confirmedLogout = new Promise<void>(resolve => { confirmed = resolve; });
    let observeLogout = false;
    const unsubscribe = client.subscribeSession(state => {
      if (observeLogout && state === "signed-out") confirmed();
    });
    observeLogout = true;
    const logout = client.api.signOut();
    await confirmedLogout;
    release(); await logout; await expect(restore).rejects.toMatchObject({ kind: "superseded" });
    unsubscribe();
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

describe("account export authorization", () => {
  it.each([
    ["/v1/me/export", "Export reauthentication required", "export_reauth"],
    ["/v1/auth/reauthenticate", "Email or password is incorrect", "export_password"],
  ])("keeps the access session for a known operation-specific 401 on %s", async (path, detail, code) => {
    const fetch = vi.fn().mockResolvedValueOnce(response(result("valid-session"))).mockResolvedValueOnce(response({ detail }, 401));
    vi.stubGlobal("fetch", fetch); const client = await load();
    await client.api.signIn("synthetic@example.test", "synthetic-password", false);
    await expect(client.request(path)).rejects.toMatchObject({ kind: "http", code });
    expect(fetch).toHaveBeenCalledTimes(2); expect(client.getSessionState()).toBe("active"); expect(client.isCurrentAccessToken("valid-session")).toBe(true);
  });
  it("still revokes an invalid access session on the export endpoint", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(result("invalid-session"))).mockResolvedValue(response({ detail: "Session expired or revoked" }, 401));
    vi.stubGlobal("fetch", fetch); const client = await load();
    await client.api.signIn("synthetic@example.test", "synthetic-password", false);
    await expect(client.api.exportAccount("purpose-token")).rejects.toMatchObject({ kind: "invalid" });
    expect(client.getSessionState()).toBe("reauth"); expect(client.isCurrentAccessToken("invalid-session")).toBe(false);
  });
  it("sends export credentials only in a no-store request header", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ version: 1 })); vi.stubGlobal("fetch", fetch);
    const client = await load(); await client.api.exportAccount("purpose-token");
    expect(fetch.mock.calls[0][0]).not.toContain("purpose-token");
    expect(fetch.mock.calls[0][1]).toMatchObject({ cache: "no-store", headers: { "X-Account-Export-Token": "purpose-token" } });
  });
});

describe("authenticated binary media transport", () => {
  it("refreshes an expired session and replays the binary request with the rotated token", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/login") ? response(result("old")) : response(result("new"))));
    const tokens: string[] = [];
    const transport = vi.fn(async (_url: string, init: RequestInit) => {
      tokens.push((init.headers as Record<string, string>).Authorization);
      return tokens.length === 1 ? response({ detail: "expired" }, 401) : new Response(new Blob(["synthetic-image"]));
    });
    const client = await load(); await client.api.signIn("a@example.test", "synthetic-password", false);
    const blob = await client.requestBlob("/v1/me/media/id/thumbnail", { transport });
    expect(await blob.text()).toBe("synthetic-image");
    expect(tokens).toEqual(["Bearer old", "Bearer new"]);
  });
  it("does not replay a delayed binary response as another account", async () => {
    let release!: (value: Response) => void, logins = 0;
    const pending = new Promise<Response>(resolve => { release = resolve; });
    vi.stubGlobal("fetch", vi.fn(async () => response(result(++logins === 1 ? "a" : "b"))));
    const transport = vi.fn().mockReturnValue(pending);
    const client = await load(); await client.api.signIn("a@example.test", "synthetic-password", false);
    const old = client.requestBlob("/v1/me/media/id/thumbnail", { transport });
    await client.api.signIn("b@example.test", "synthetic-password", false);
    release(response({}, 401)); await expect(old).rejects.toMatchObject({ kind: "superseded" });
    expect(transport).toHaveBeenCalledTimes(1); expect(client.isCurrentAccessToken("b")).toBe(true);
  });
});
