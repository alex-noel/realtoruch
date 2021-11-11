import { beforeEach, describe, expect, it, vi } from "vitest";

const f = vi.hoisted(() => ({ platform: { OS: "ios" }, store: new Map<string, string>(), failRead: false, failWrite: false }));
vi.mock("react-native", () => ({ Platform: f.platform }));
vi.mock("expo-secure-store", () => ({
  getItemAsync: async (key: string) => { if (f.failRead) throw Error("storage"); return f.store.get(key) ?? null; },
  setItemAsync: async (key: string, value: string) => { if (f.failWrite) throw Error("storage"); f.store.set(key, value); },
  deleteItemAsync: async (key: string) => { f.store.delete(key); },
}));
const result = (access: string, refresh = "rotated") => ({ access_token: access, refresh_token: refresh, user: { id: "1", email: "x@example.test", email_verified: true } });
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
async function load() { return import("../src/api"); }
beforeEach(() => { vi.resetModules(); f.platform.OS = "ios"; f.store.clear(); f.failRead = false; f.failWrite = false; vi.unstubAllGlobals(); });

describe("session resilience", () => {
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
    const client = await load(); const states: string[] = []; client.subscribeSession(s => states.push(s));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "invalid" }); expect(fetch).not.toHaveBeenCalled(); expect(states.at(-1)).toBe("reauth");
  });
  it("preserves storage on read failure and requires sign in after rotated token write failure", async () => {
    f.store.set("realtoruch_refresh", "original"); f.failRead = true;
    const client = await load(); await expect(client.restoreToken()).rejects.toMatchObject({ kind: "storage" }); expect(f.store.get("realtoruch_refresh")).toBe("original");
    f.failRead = false; f.failWrite = true; vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(result("new"))));
    await expect(client.restoreToken()).rejects.toMatchObject({ kind: "storage" }); expect(f.store.has("realtoruch_refresh")).toBe(false);
  });
});
