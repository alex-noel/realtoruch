import { beforeEach, expect, it, vi } from "vitest";

const f = vi.hoisted(() => ({ revision: 2, enabled: false, request: vi.fn(), unregister: vi.fn(), register: vi.fn(async () => ({ id: "server-id" })), revoke: vi.fn(async () => {}), dispose: vi.fn() }));
vi.mock("../src/api", () => ({ getSessionRevision: () => f.revision, request: f.request, capturePushRegistration: () => ({ register: f.register, revoke: f.revoke, dispose: f.dispose }) }));
vi.mock("@react-native-async-storage/async-storage", () => ({ default: { getItem: vi.fn(async () => null), setItem: vi.fn(async () => {}), removeItem: vi.fn(async () => {}), getAllKeys: vi.fn(async () => []) } }));
vi.mock("expo-secure-store", () => ({ getItemAsync: vi.fn(async () => null), setItemAsync: vi.fn(async () => {}), deleteItemAsync: vi.fn(async () => {}) }));
vi.mock("expo-constants", () => ({ default: { easConfig: { projectId: "project" } } }));
vi.mock("react-native", () => ({ Platform: { OS: "ios" } }));
vi.mock("expo-notifications", () => ({
  setNotificationHandler: vi.fn(), getPermissionsAsync: vi.fn(async () => ({ granted: false, status: "undetermined", canAskAgain: true })),
  requestPermissionsAsync: vi.fn(async () => ({ granted: true })), getExpoPushTokenAsync: vi.fn(async () => ({ data: "expo-token" })),
  setNotificationChannelAsync: vi.fn(async () => {}), unregisterForNotificationsAsync: f.unregister,
  addNotificationReceivedListener: vi.fn(), addNotificationResponseReceivedListener: vi.fn(), getLastNotificationResponseAsync: vi.fn(), clearLastNotificationResponseAsync: vi.fn(),
  AndroidImportance: { DEFAULT: 3 },
}));
import { disablePush, enablePush, pushStatus } from "../src/pushClient";
import * as Notifications from "expo-notifications";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

beforeEach(() => {
  f.revision = 2; f.enabled = false; f.unregister.mockReset().mockResolvedValue(undefined);
  f.request.mockReset().mockImplementation(async (path: string) => path.includes("config") ? { expo_push_enabled: f.enabled } : { id: "server-id" });
  vi.mocked(AsyncStorage.getItem).mockReset().mockResolvedValue(null);
  vi.mocked(AsyncStorage.setItem).mockReset().mockResolvedValue(undefined);
  vi.mocked(AsyncStorage.removeItem).mockReset().mockResolvedValue(undefined);
  vi.mocked(SecureStore.getItemAsync).mockReset().mockResolvedValue(null);
  vi.mocked(SecureStore.setItemAsync).mockReset().mockResolvedValue(undefined);
  vi.mocked(SecureStore.deleteItemAsync).mockReset().mockResolvedValue(undefined);
  f.register.mockReset().mockResolvedValue({ id: "server-id" });
  f.revoke.mockReset().mockResolvedValue(undefined);
  f.dispose.mockReset();
  vi.mocked(Notifications.requestPermissionsAsync).mockClear();
  vi.mocked(Notifications.setNotificationChannelAsync).mockClear();
  (Platform as { OS: string }).OS = "ios";
});

it("creates the Android channel after configuration and before requesting permission", async () => {
  (Platform as { OS: string }).OS = "android";
  f.enabled = true;
  vi.mocked(Notifications.getPermissionsAsync).mockResolvedValue({ granted: false, status: "undetermined", canAskAgain: true } as any);
  await enablePush("user");
  expect(f.request.mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(Notifications.setNotificationChannelAsync).mock.invocationCallOrder[0]);
  expect(vi.mocked(Notifications.setNotificationChannelAsync).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(Notifications.requestPermissionsAsync).mock.invocationCallOrder[0]);
});

it("does not ask for permission while server push is unavailable", async () => {
  (Platform as { OS: string }).OS = "android";
  expect((await pushStatus("user")).state).toBe("unavailable");
  await expect(enablePush("user")).rejects.toThrow("not configured");
  expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
  expect(Notifications.setNotificationChannelAsync).not.toHaveBeenCalled();
});

it("revokes native registration after partial registration even without a marker", async () => {
  await disablePush();
  expect(f.unregister).toHaveBeenCalled();
});

it("serializes mutations and prevents an old account cleanup deleting a newer marker", async () => {
  f.enabled = true;
  vi.mocked(AsyncStorage.getItem).mockImplementation(async key => key === "realtoruch.push.v1" ? JSON.stringify({ id: "old-id", owner: "old-user" }) : null);
  let release!: () => void;
  f.unregister.mockImplementation(() => new Promise<void>((resolve) => { release = resolve; }));
  const oldCleanup = import("../src/pushClient").then(({ disablePush }) => disablePush("old-user"));
  await vi.waitFor(() => expect(f.unregister).toHaveBeenCalled());
  f.revision++;
  const newerEnable = enablePush("new-user");
  release();
  await expect(oldCleanup).rejects.toThrow("account changed");
  await newerEnable;
  expect(AsyncStorage.setItem).toHaveBeenCalledWith("realtoruch.push.v1", JSON.stringify({ id: "server-id", owner: "new-user" }));
});

it("does not report subscribed after the native token rotates", async () => {
  f.enabled = true;
  vi.mocked(Notifications.getPermissionsAsync).mockResolvedValue({ granted: true, status: "granted", canAskAgain: false } as any);
  vi.mocked(AsyncStorage.getItem).mockImplementation(async key => key === "realtoruch.push.v1" ? JSON.stringify({ id: "old-server-id", owner: "user" }) : null);
  vi.mocked(SecureStore.getItemAsync).mockResolvedValue("previous-expo-token");
  expect((await pushStatus("user")).state).toBe("available");
});

it("unregisters the local token before releasing a stale registration after account switch", async () => {
  f.enabled = true;
  let resolvePost!: (value: { id: string }) => void;
  f.register.mockImplementation(() => new Promise((resolve) => { resolvePost = resolve; }));
  const action = enablePush("old-user");
  await vi.waitFor(() => expect(f.register).toHaveBeenCalled());
  f.revision++;
  resolvePost({ id: "orphan-id" });
  await expect(action).rejects.toThrow("account changed");
  expect(f.unregister).toHaveBeenCalled();
  expect(f.revoke).toHaveBeenCalledOnce();
  expect(AsyncStorage.setItem).not.toHaveBeenCalledWith("realtoruch.push.v1", expect.anything());
});

it("retains a pending owner marker when native server revocation fails", async () => {
  const raw = JSON.stringify({ id: "old-id", owner: "old-user" });
  vi.mocked(AsyncStorage.getItem).mockImplementation(async key => key === "realtoruch.push.v1" ? raw : null);
  f.request.mockRejectedValue(Error("offline"));
  await expect(disablePush("old-user")).rejects.toThrow("offline");
  expect(f.unregister).toHaveBeenCalledOnce();
  expect(AsyncStorage.setItem).toHaveBeenCalledWith("realtoruch.push.v1", JSON.stringify({ id: "old-id", owner: "old-user", pending: true }));
  expect(AsyncStorage.removeItem).not.toHaveBeenCalledWith("realtoruch.push.v1");
  vi.mocked(AsyncStorage.getItem).mockImplementation(async key => key === "realtoruch.push.v1" ? JSON.stringify({ id: "old-id", owner: "old-user", pending: true }) : null);
  expect((await pushStatus("old-user")).state).toBe("cleanup-pending");
  f.request.mockResolvedValue({ enabled: false });
  await disablePush("old-user");
  expect(AsyncStorage.removeItem).toHaveBeenCalledWith("realtoruch.push.v1");
  expect(f.register).not.toHaveBeenCalled();
});

it("compensates and restores pending evidence if the account changes during final marker removal", async () => {
  f.enabled = true;
  let release!: () => void;
  vi.mocked(AsyncStorage.removeItem).mockImplementation(key => key.endsWith("pending.old-user") ? new Promise<void>(resolve => { release = resolve; }) : Promise.resolve());
  const action = enablePush("old-user");
  await vi.waitFor(() => expect(AsyncStorage.removeItem).toHaveBeenCalledWith("realtoruch.push.v1.pending.old-user"));
  f.revision++;
  release();
  await expect(action).rejects.toThrow("account changed");
  expect(f.revoke).toHaveBeenCalledOnce();
  expect(vi.mocked(AsyncStorage.setItem).mock.calls.filter(([key]) => key === "realtoruch.push.v1.pending.old-user")).toHaveLength(2);
});
