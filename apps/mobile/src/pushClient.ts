import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { capturePushRegistration, getSessionRevision, request } from "./api";
import { pushSubscriptionId } from "./pushDigest";

const KEY = "realtoruch.push.v1";
const TOKEN_KEY = "realtoruch.push.token.v1";
const PENDING = `${KEY}.pending.`;
type PushMarker = { id: string; owner: string; pending?: boolean };
export type PushCapability =
  | { state: "available"; message?: string }
  | { state: "subscribed" }
  | { state: "cleanup-pending"; message: string }
  | { state: "denied"; message: string }
  | { state: "unavailable"; message: string }
  | { state: "unknown"; message: string };

let mutationQueue: Promise<void> = Promise.resolve();
function serialize<T>(run: () => Promise<T>): Promise<T> {
  const result = mutationQueue.then(run, run);
  mutationQueue = result.then(() => undefined, () => undefined);
  return result;
}
function assertRevision(revision: number) {
  if (getSessionRevision() !== revision)
    throw new Error("Your account changed. Check device alert settings again.");
}
function projectId() {
  return Constants.easConfig?.projectId || Constants.expoConfig?.extra?.eas?.projectId;
}
function parseMarker(raw: string | null): PushMarker | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" && value !== null &&
      typeof (value as PushMarker).id === "string" &&
      typeof (value as PushMarker).owner === "string"
    ) return value as PushMarker;
  } catch {
    // Legacy IDs remain available for revocation but are never trusted as subscribed.
  }
  return { id: raw, owner: "" };
}
function configuredProject() {
  return projectId() || null;
}
async function config() {
  return request<{ expo_push_enabled: boolean }>("/v1/notifications/config");
}
async function currentToken(id: string) {
  return (await Notifications.getExpoPushTokenAsync({ projectId: id })).data;
}

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function pushStatus(owner: string): Promise<PushCapability> {
  const revision = getSessionRevision();
  try {
    const pending = await AsyncStorage.getItem(PENDING + encodeURIComponent(owner));
    const pendingMarker = parseMarker(await AsyncStorage.getItem(KEY));
    assertRevision(revision);
    if (pending || (pendingMarker?.owner === owner && pendingMarker.pending)) return { state: "cleanup-pending", message: "Device alert removal could not be confirmed. Retry removal." };
    const settings = await config();
    assertRevision(revision);
    if (!settings.expo_push_enabled)
      return {
        state: "unavailable",
        message: "Mobile push is not configured yet. Your alerts are saved in the inbox.",
      };
    const id = configuredProject();
    if (!id)
      return {
        state: "unavailable",
        message: "Use a configured development or release build to enable mobile push.",
      };
    const permission = await Notifications.getPermissionsAsync();
    assertRevision(revision);
    if (!permission.granted) {
      if (permission.status === "denied" && !permission.canAskAgain)
        return {
          state: "denied",
          message: "Notifications are blocked. Allow them in device settings to enable alerts.",
        };
      return { state: "available" };
    }
    const raw = await AsyncStorage.getItem(KEY);
    assertRevision(revision);
    const marker = parseMarker(raw);
    if (!marker || marker.owner !== owner || marker.pending) return { state: "available" };
    const token = await currentToken(id);
    assertRevision(revision);
    if (await SecureStore.getItemAsync(TOKEN_KEY) !== token) return { state: "available" };
    assertRevision(revision);
    return { state: "subscribed" };
  } catch (error) {
    if (getSessionRevision() !== revision)
      return { state: "unknown", message: "Account changed while checking device alerts." };
    return {
      state: "unknown",
      message: error instanceof Error
        ? error.message
        : "Could not check device alert settings.",
    };
  }
}

export function enablePush(owner = "") {
  const revision = getSessionRevision();
  return serialize(async () => {
    let tokenReady = false;
    let registration: ReturnType<typeof capturePushRegistration> | null = null;
    let pendingRecord: { key: string; value: string } | null = null;
    try {
    assertRevision(revision);
    if (!owner) throw new Error("Sign in again to enable device alerts.");
    const settings = await config();
    assertRevision(revision);
    if (!settings.expo_push_enabled)
      throw new Error("Mobile push is not configured yet. Your alerts are saved in the inbox.");
    const id = configuredProject();
    if (!id)
      throw new Error("Use a configured development or release build to enable mobile push.");
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("rentals", {
        name: "Rental alerts",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
      assertRevision(revision);
    }
    const permission = await Notifications.getPermissionsAsync();
    assertRevision(revision);
    let granted = permission.granted;
    if (!granted && permission.status === "denied" && !permission.canAskAgain)
      throw new Error("Notifications are blocked. Allow them in device settings to enable alerts.");
    if (!granted && permission.canAskAgain) {
      const response = await Notifications.requestPermissionsAsync();
      assertRevision(revision);
      granted = response.granted;
    }
    if (!granted)
      throw new Error("Allow notifications in device settings to enable alerts.");
    const token = await currentToken(id);
    tokenReady = true;
    assertRevision(revision);
    const subscriptionId = pushSubscriptionId(token);
    const pendingKey = PENDING + encodeURIComponent(owner);
    const oldPending = parseMarker(await AsyncStorage.getItem(pendingKey));
    assertRevision(revision);
    const previousRaw = await AsyncStorage.getItem(KEY);
    assertRevision(revision);
    const previous = parseMarker(previousRaw);
    if (previous?.owner === owner && previous.pending) {
      try { await request(`/v1/me/push-subscriptions/${encodeURIComponent(previous.id)}`, { method: "DELETE" }); }
      catch (error) { if ((error as { status?: number }).status !== 404) throw error; }
      assertRevision(revision);
      if (await AsyncStorage.getItem(KEY) === previousRaw) await AsyncStorage.removeItem(KEY);
      assertRevision(revision);
    }
    if (oldPending) {
      try { await request(`/v1/me/push-subscriptions/${encodeURIComponent(oldPending.id)}`, { method: "DELETE" }); }
      catch (error) { if ((error as { status?: number }).status !== 404) throw error; }
      await AsyncStorage.removeItem(pendingKey);
      assertRevision(revision);
    }
    pendingRecord = { key: pendingKey, value: JSON.stringify({ id: subscriptionId, owner, pending: true }) };
    await AsyncStorage.setItem(pendingRecord.key, pendingRecord.value);
    assertRevision(revision);
    registration = capturePushRegistration({ kind: "expo", token });
    const result = await registration.register();
    if (getSessionRevision() !== revision) {
      throw new Error("Your account changed. Check device alert settings again.");
    }
    const marker = JSON.stringify({ id: result.id, owner });
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    assertRevision(revision);
    await AsyncStorage.setItem(KEY, marker);
    assertRevision(revision);
    await AsyncStorage.removeItem(pendingKey);
    assertRevision(revision);
    } catch (error) {
      if (registration && pendingRecord) {
        try { await AsyncStorage.setItem(pendingRecord.key, pendingRecord.value); } catch { /* Cleanup is reported as unconfirmed. */ }
      }
      if (registration) {
        try { await registration.revoke(); } catch { /* Pending evidence remains for a same-owner retry. */ }
      }
      if (tokenReady) {
        try {
          await Notifications.unregisterForNotificationsAsync();
          await SecureStore.deleteItemAsync(TOKEN_KEY);
        } catch { /* The local token can no longer receive if unregister succeeds. */ }
      }
      throw error;
    } finally { registration?.dispose(); }
  });
}

export function disablePush(owner?: string) {
  const revision = getSessionRevision();
  return serialize(async () => {
    assertRevision(revision);
    const raw = await AsyncStorage.getItem(KEY);
    assertRevision(revision);
    const marker = parseMarker(raw);
    const keys = await AsyncStorage.getAllKeys();
    assertRevision(revision);
    const pendingKeys = keys.filter((key) => key.startsWith(PENDING));
    const pending = await Promise.all(pendingKeys.map(async (key) => ({ key, marker: parseMarker(await AsyncStorage.getItem(key)) })));
    assertRevision(revision);
    const otherOwner = !!(owner && ((marker?.owner && marker.owner !== owner) || (!marker && pending.some(entry => entry.marker?.owner && entry.marker.owner !== owner))));
    const targets = [ ...(marker && !otherOwner ? [{ key: KEY, marker }] : []), ...pending.filter((entry) => entry.marker && (!owner || entry.marker.owner === owner)) ];
    let requestError: unknown;
    for (const target of targets) {
      try {
        await request(`/v1/me/push-subscriptions/${encodeURIComponent(target.marker!.id)}`, {
          method: "DELETE",
        });
        assertRevision(revision);
        await AsyncStorage.removeItem(target.key);
        assertRevision(revision);
      } catch (error) {
        if (getSessionRevision() !== revision) return;
        if ((error as { status?: number }).status === 404) {
          if (target.key === KEY || !owner || target.marker!.owner === owner) await AsyncStorage.removeItem(target.key);
        } else requestError ||= error;
      }
    }
    if (getSessionRevision() !== revision) return;
    if (otherOwner) { if (requestError) throw requestError; return; }
    const id = configuredProject();
    if (id) {
      try { await Notifications.unregisterForNotificationsAsync(); }
      catch (error) {
        if (getSessionRevision() === revision && marker) await AsyncStorage.setItem(KEY, JSON.stringify({ ...marker, pending: true }));
        throw error;
      }
      assertRevision(revision);
    }
    const current = await AsyncStorage.getItem(KEY);
    assertRevision(revision);
    if (requestError && current === raw && marker) {
      await AsyncStorage.setItem(KEY, JSON.stringify({ ...marker, pending: true }));
      assertRevision(revision);
    }
    if (!requestError && current === raw) {
      await AsyncStorage.removeItem(KEY);
      assertRevision(revision);
    }
    if (!requestError) {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      assertRevision(revision);
    }
    if (requestError) throw requestError;
  });
}

export function listenForPush(
  onOpen: (id: string) => void,
  onUpdate: () => void,
) {
  let active = true;
  const open = (response: Notifications.NotificationResponse) => {
    const id = response.notification.request.content.data?.listing_id;
    if (active && typeof id === "string") {
      onOpen(id);
      Notifications.clearLastNotificationResponseAsync().catch(() => {});
    }
  };
  const receive = Notifications.addNotificationReceivedListener(onUpdate);
  const response = Notifications.addNotificationResponseReceivedListener(open);
  Notifications.getLastNotificationResponseAsync()
    .then((value) => {
      if (value) open(value);
    })
    .catch(() => {});
  return () => {
    active = false;
    receive.remove();
    response.remove();
  };
}
