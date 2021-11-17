import { beforeEach, expect, it, vi } from "vitest";

const f = vi.hoisted(() => ({ revision: 3, config: { web_push_enabled: false, vapid_public_key: "AQ" }, request: vi.fn(), register: vi.fn(), revoke: vi.fn(), dispose: vi.fn() }));
vi.mock("../src/api", () => ({ getSessionRevision: () => f.revision, request: f.request, capturePushRegistration: () => ({ register: f.register, revoke: f.revoke, dispose: f.dispose }) }));
import { disablePush, enablePush, pushStatus } from "../src/pushClient.web";

const subscription = { endpoint: "https://push.example/device", toJSON: () => ({ endpoint: "https://push.example/device", keys: { p256dh: "a", auth: "b" } }), unsubscribe: vi.fn(async () => true) };
const manager = { getSubscription: vi.fn(async (): Promise<any> => null), subscribe: vi.fn(async (): Promise<any> => subscription) };
const registration = { pushManager: manager };
const serviceWorker = { register: vi.fn(async () => registration), ready: Promise.resolve(registration), getRegistration: vi.fn(async () => registration) };

beforeEach(() => {
  f.revision = 3;
  f.config = { web_push_enabled: false, vapid_public_key: "AQ" };
  f.request.mockReset().mockImplementation(async (path: string) => path.includes("config") ? f.config : { id: "digest" });
  f.register.mockReset().mockResolvedValue({ id: "digest" });
  f.revoke.mockReset().mockResolvedValue(undefined);
  f.dispose.mockReset();
  manager.getSubscription.mockReset().mockResolvedValue(null);
  manager.subscribe.mockReset().mockResolvedValue(subscription);
  serviceWorker.register.mockClear();
  serviceWorker.getRegistration.mockReset().mockResolvedValue(registration);
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { serviceWorker } });
  const browserNotification = { permission: "default", requestPermission: vi.fn(async () => "granted") };
  Object.defineProperty(globalThis, "window", { configurable: true, value: { PushManager: function PushManager() {}, Notification: browserNotification } });
  Object.defineProperty(globalThis, "Notification", { configurable: true, value: browserNotification });
  const store: Record<string, any> = {};
  Object.defineProperties(store, { getItem: { value: (k: string) => store[k] ?? null }, setItem: { value: (k: string, v: string) => { store[k] = v; } }, removeItem: { value: (k: string) => { delete store[k]; } } });
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: store });
  subscription.unsubscribe.mockReset().mockResolvedValue(true);
});

it("checks configuration before prompting or registering the browser", async () => {
  const status = await pushStatus("account");
  expect(status.state).toBe("unavailable");
  await expect(enablePush("account")).rejects.toThrow("not configured");
  expect(Notification.requestPermission).not.toHaveBeenCalled();
  expect(serviceWorker.register).not.toHaveBeenCalled();
});

it("does not trust a stale marker without a matching real browser subscription", async () => {
  f.config.web_push_enabled = true;
  localStorage.setItem("realtoruch.push.v1", JSON.stringify({ id: "digest", owner: "account" }));
  expect((await pushStatus("account")).state).toBe("available");
});

it("reuses an existing browser subscription after a recoverable registration failure", async () => {
  f.config.web_push_enabled = true;
  Object.defineProperty(Notification, "permission", { configurable: true, value: "granted" });
  manager.getSubscription.mockResolvedValue(subscription);
  f.register.mockRejectedValue(Error("offline"));
  await expect(enablePush("account")).rejects.toThrow("offline");
  expect(manager.subscribe).not.toHaveBeenCalled();
});

it("revokes a partial local subscription on logout even when server registration left no marker", async () => {
  manager.getSubscription.mockResolvedValue(subscription);
  await disablePush();
  expect(subscription.unsubscribe).toHaveBeenCalled();
});

it("deletes and unsubscribes a matching active subscription on logout", async () => {
  const raw = JSON.stringify({ id: "old-id", owner: "account" });
  localStorage.setItem("realtoruch.push.v1", raw);
  manager.getSubscription.mockResolvedValue(subscription);
  await disablePush("account");
  expect(f.request).toHaveBeenCalledWith("/v1/me/push-subscriptions/old-id", { method: "DELETE" });
  expect(subscription.unsubscribe).toHaveBeenCalledOnce();
  expect(localStorage.getItem("realtoruch.push.v1")).toBeNull();
});

it("preserves another tab's account and subscription", async () => {
  const raw = JSON.stringify({ id: "new-id", owner: "new-account" });
  localStorage.setItem("realtoruch.push.v1", raw);
  manager.getSubscription.mockResolvedValue(subscription);
  await disablePush("old-account");
  expect(subscription.unsubscribe).not.toHaveBeenCalled();
  expect(localStorage.getItem("realtoruch.push.v1")).toBe(raw);
});

it("does not unsubscribe when another tab replaces the marker during lookup", async () => {
  localStorage.setItem("realtoruch.push.v1", JSON.stringify({ id: "old-id", owner: "old-account" }));
  let release!: (value: typeof registration) => void;
  serviceWorker.getRegistration.mockImplementation(() => new Promise(resolve => { release = resolve; }));
  manager.getSubscription.mockResolvedValue(subscription);
  const action = disablePush("old-account");
  await vi.waitFor(() => expect(serviceWorker.getRegistration).toHaveBeenCalled());
  const newer = JSON.stringify({ id: "new-id", owner: "new-account" });
  localStorage.setItem("realtoruch.push.v1", newer);
  release(registration);
  await action;
  expect(subscription.unsubscribe).not.toHaveBeenCalled();
  expect(localStorage.getItem("realtoruch.push.v1")).toBe(newer);
});

it("uses the browser lock for cross-tab push mutations when available", async () => {
  const request = vi.fn(async (_name: string, action: () => Promise<void>) => action());
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { serviceWorker, locks: { request } } });
  await disablePush("account");
  expect(request).toHaveBeenCalledWith("realtoruch-push", expect.any(Function));
});

it("retains a retryable owner marker after a failed delete", async () => {
  localStorage.setItem("realtoruch.push.v1", JSON.stringify({ id: "old-id", owner: "account" }));
  manager.getSubscription.mockResolvedValue(subscription);
  f.request.mockRejectedValue(Error("offline"));
  await expect(disablePush("account")).rejects.toThrow("offline");
  expect(JSON.parse(localStorage.getItem("realtoruch.push.v1")!)).toMatchObject({ id: "old-id", owner: "account", pending: true });
  expect(subscription.unsubscribe).toHaveBeenCalledOnce();
  expect((await pushStatus("account")).state).toBe("cleanup-pending");
  f.request.mockResolvedValue({ enabled: false });
  await disablePush("account");
  expect(localStorage.getItem("realtoruch.push.v1")).toBeNull();
  expect(f.register).not.toHaveBeenCalled();
});

it("leaves pending evidence and compensates after an ambiguous POST", async () => {
  f.config.web_push_enabled = true;
  f.register.mockRejectedValue(Error("connection lost"));
  await expect(enablePush("account")).rejects.toThrow("connection lost");
  expect(f.revoke).toHaveBeenCalledOnce();
  expect(localStorage.getItem("realtoruch.push.v1.pending.account")).toBeTruthy();
});

it("retains a retry marker when the browser refuses to unsubscribe", async () => {
  localStorage.setItem("realtoruch.push.v1", JSON.stringify({ id: "old-id", owner: "account" }));
  manager.getSubscription.mockResolvedValue(subscription);
  subscription.unsubscribe.mockResolvedValue(false);
  await expect(disablePush("account")).rejects.toThrow("could not be confirmed");
  expect(JSON.parse(localStorage.getItem("realtoruch.push.v1")!)).toMatchObject({ id: "old-id", owner: "account", pending: true });
});
