import { beforeEach, expect, it, vi } from "vitest";
import { pushSubscriptionId } from "../src/pushDigest";
vi.mock("react-native", () => ({ Platform: { OS: "ios" } }));
vi.mock("expo-secure-store", () => ({ getItemAsync: vi.fn(), setItemAsync: vi.fn(), deleteItemAsync: vi.fn() }));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const login = (token: string) => ({ access_token: token, refresh_token: "refresh", user: { id: token, email: "fixture@example.test", email_verified: true } });
beforeEach(() => { vi.resetModules(); vi.unstubAllGlobals(); });

it("compensates a delayed old-account registration with the captured bearer only", async () => {
  let release!: (response: Response) => void, logins = 0;
  const pending = new Promise<Response>(resolve => { release = resolve; });
  const calls: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    if (url.endsWith("/login")) return json(login(++logins === 1 ? "old" : "new"));
    if (init.method === "POST") return pending;
    return json({ enabled: false });
  }));
  const client = await import("../src/api");
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  const payload = { kind: "expo", token: "fixture-token" } as const;
  const operation = client.capturePushRegistration(payload);
  const registration = operation.register();
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  const id = pushSubscriptionId(payload.token);
  release(json({ id }));
  expect(await registration).toEqual({ id });
  await operation.revoke();
  const mutations = calls.filter(call => call.url.includes("/push-subscriptions"));
  expect(mutations.map(call => (call.init.headers as Record<string, string>).Authorization)).toEqual(["Bearer old", "Bearer old"]);
  expect(mutations.map(call => call.init.credentials)).toEqual(["omit", "omit"]);
  expect(mutations.map(call => call.init.redirect)).toEqual(["error", "error"]);
  expect(mutations[1].url).toMatch(new RegExp(`/v1/me/push-subscriptions/${id}$`));
  expect(client.isCurrentAccessToken("new")).toBe(true);
  operation.dispose();
  await expect(operation.register()).rejects.toMatchObject({ kind: "superseded" });
});

it("does not refresh or invalidate the current session when compensation is unauthorized", async () => {
  let requests = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    requests++;
    return url.endsWith("/login") ? json(login("old")) : json({ detail: "expired" }, 401);
  }));
  const client = await import("../src/api");
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  const operation = client.capturePushRegistration({ kind: "expo", token: "fixture-token" });
  await expect(operation.register()).rejects.toMatchObject({ status: 401 });
  expect(requests).toBe(2);
  expect(client.isCurrentAccessToken("old")).toBe(true);
  operation.dispose();
});

it("compensates only the captured payload after an invalid or lost response", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/login") ? json(login("old")) : json({ id: "a".repeat(64) })));
  const client = await import("../src/api");
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  const operation = client.capturePushRegistration({ kind: "expo", token: "fixture-token" });
  await expect(operation.register()).rejects.toThrow("could not be confirmed");
  await expect(operation.revoke()).resolves.toBeUndefined();
  operation.dispose();
});

it("does not start registration after the captured account changes", async () => {
  let logins = 0;
  const fetch = vi.fn(async () => json(login(++logins === 1 ? "old" : "new")));
  vi.stubGlobal("fetch", fetch);
  const client = await import("../src/api");
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  const operation = client.capturePushRegistration({ kind: "expo", token: "fixture-token" });
  await client.api.signIn("fixture@example.test", "fixture-password", false);
  await expect(operation.register()).rejects.toMatchObject({ kind: "superseded" });
  await expect(operation.revoke()).rejects.toThrow("could not be confirmed");
  expect(fetch).toHaveBeenCalledTimes(2);
  operation.dispose();
});
