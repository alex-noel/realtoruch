import { capturePushRegistration, getSessionRevision, request } from "./api";
import { pushSubscriptionId } from "./pushDigest";

const KEY = "realtoruch.push.v1";
const PENDING = `${KEY}.pending.`;
type Marker = { id: string; owner: string; pending?: boolean };
export type PushCapability =
  | { state: "available"; message?: string }
  | { state: "subscribed" }
  | { state: "cleanup-pending"; message: string }
  | { state: "denied"; message: string }
  | { state: "unavailable"; message: string }
  | { state: "unknown"; message: string };
let queue: Promise<void> = Promise.resolve();
function serialize<T>(run: () => Promise<T>): Promise<T> {
  const locked = () => navigator.locks?.request
    ? navigator.locks.request("realtoruch-push", run) as unknown as Promise<T>
    : run();
  const task = queue.then(locked, locked);
  queue = task.then(() => undefined, () => undefined);
  return task;
}
function check(revision: number) {
  if (getSessionRevision() !== revision) throw new Error("Your account changed. Check device alert settings again.");
}
function parse(raw: string | null): Marker | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value === "object" && value !== null && typeof (value as Marker).id === "string" && typeof (value as Marker).owner === "string") return value as Marker;
  } catch { /* Legacy IDs are revocable but never trusted as active. */ }
  return { id: raw, owner: "" };
}
function supported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}
async function config() {
  return request<{ web_push_enabled: boolean; vapid_public_key: string }>("/v1/notifications/config");
}
async function currentSubscription() {
  const registration = await navigator.serviceWorker?.getRegistration();
  return { registration, subscription: await registration?.pushManager.getSubscription() };
}
export async function pushStatus(owner: string): Promise<PushCapability> {
  const revision = getSessionRevision();
  try {
    const pendingMarker = parse(localStorage.getItem(KEY));
    if (localStorage.getItem(PENDING + encodeURIComponent(owner)) || (pendingMarker?.owner === owner && pendingMarker.pending)) return { state: "cleanup-pending", message: "Device alert removal could not be confirmed. Retry removal." };
    if (!supported()) return { state: "unavailable", message: "This browser does not support push notifications. Your in-app inbox still works." };
    const settings = await config(); check(revision);
    if (!settings.web_push_enabled) return { state: "unavailable", message: "Browser push is not configured yet. Your alerts are saved in the inbox." };
    if (Notification.permission === "denied") return { state: "denied", message: "Notifications are blocked. Allow them in browser settings to enable alerts." };
    if (Notification.permission !== "granted") return { state: "available" };
    const { subscription } = await currentSubscription(); check(revision);
    const marker = parse(localStorage.getItem(KEY));
    if (!subscription || !marker || marker.owner !== owner || marker.pending) return { state: "available" };
    const id = pushSubscriptionId(subscription.endpoint); check(revision);
    return id === marker.id ? { state: "subscribed" } : { state: "available" };
  } catch (error) {
    return { state: "unknown", message: error instanceof Error ? error.message : "Could not check device alert settings." };
  }
}
export function enablePush(owner = "") {
  const revision = getSessionRevision();
  return serialize(async () => {
    let localSubscription: PushSubscription | null = null;
    const startingMarker = localStorage.getItem(KEY);
    try {
    check(revision);
    if (!owner) throw new Error("Sign in again to enable device alerts.");
    if (!supported()) throw new Error("This browser does not support push notifications. Your in-app inbox still works.");
    const settings = await config(); check(revision);
    if (!settings.web_push_enabled) throw new Error("Browser push is not configured yet. Your alerts are saved in the inbox.");
    if (Notification.permission === "denied") throw new Error("Notifications are blocked. Allow them in browser settings to enable alerts.");
    if (Notification.permission !== "granted" && await Notification.requestPermission() !== "granted")
      throw new Error("Allow notifications in browser settings to enable alerts.");
    check(revision);
    await navigator.serviceWorker.register("/service-worker.js"); check(revision);
    const registration = await navigator.serviceWorker.ready; check(revision);
    const raw = atob(settings.vapid_public_key.replace(/-/g, "+").replace(/_/g, "/"));
    const key = Uint8Array.from(raw, (character) => character.charCodeAt(0));
    const subscription = (await registration.pushManager.getSubscription()) || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    localSubscription = subscription;
    check(revision);
    const json = subscription.toJSON();
    const id = pushSubscriptionId(json.endpoint || "");
    const pendingKey = PENDING + encodeURIComponent(owner);
    const oldPending = parse(localStorage.getItem(pendingKey));
    const previous = parse(localStorage.getItem(KEY));
    if (previous?.owner === owner && previous.pending) {
      try { await request(`/v1/me/push-subscriptions/${encodeURIComponent(previous.id)}`, { method: "DELETE" }); }
      catch (error) { if ((error as { status?: number }).status !== 404) throw error; }
      check(revision);
      if (parse(localStorage.getItem(KEY))?.id === previous.id) localStorage.removeItem(KEY);
    }
    if (oldPending) {
      try { await request(`/v1/me/push-subscriptions/${encodeURIComponent(oldPending.id)}`, { method: "DELETE" }); }
      catch (error) { if ((error as { status?: number }).status !== 404) throw error; }
      localStorage.removeItem(pendingKey);
      check(revision);
    }
    localStorage.setItem(pendingKey, JSON.stringify({ id, owner, pending: true }));
    check(revision);
    const registrationCapability = capturePushRegistration({ kind: "web", endpoint: json.endpoint || "", keys: json.keys });
    try {
      const result = await registrationCapability.register();
      if (getSessionRevision() !== revision) {
        throw new Error("Your account changed. Check device alert settings again.");
      }
      localStorage.setItem(KEY, JSON.stringify({ id: result.id, owner }));
      check(revision);
      localStorage.removeItem(pendingKey);
    } catch (error) {
      try { await registrationCapability.revoke(); } catch { /* Pending evidence remains for a same-owner retry. */ }
      throw error;
    } finally { registrationCapability.dispose(); }
    } catch (error) {
      if (localSubscription && getSessionRevision() !== revision && localStorage.getItem(KEY) === startingMarker) {
        try { await localSubscription.unsubscribe(); } catch { /* Keep the account fence; the browser may retry cleanup later. */ }
      }
      throw error;
    }
  });
}
export function disablePush(owner?: string) {
  const revision = getSessionRevision();
  return serialize(async () => {
    check(revision);
    const raw = localStorage.getItem(KEY);
    const marker = parse(raw);
    const allPending = Object.keys(localStorage).filter((key) => key.startsWith(PENDING)).map((key) => ({ key, value: parse(localStorage.getItem(key)) }));
    const otherOwner = !!(owner && ((marker?.owner && marker.owner !== owner) || (!marker && allPending.some(entry => entry.value?.owner && entry.value.owner !== owner))));
    const pending = allPending.filter((entry) => entry.value && (!owner || entry.value.owner === owner));
    const targets = [ ...(marker && (!owner || !marker.owner || marker.owner === owner) ? [{ key: KEY, value: marker }] : []), ...pending ];
    let failure: unknown;
    let removeActiveMarker = false;
    for (const target of targets) {
      try {
        await request(`/v1/me/push-subscriptions/${encodeURIComponent(target.value!.id)}`, { method: "DELETE" });
        check(revision);
        if (target.key === KEY) removeActiveMarker = true;
        else if (localStorage.getItem(target.key)) localStorage.removeItem(target.key);
      } catch (error) {
        if (getSessionRevision() !== revision) return;
        if ((error as { status?: number }).status === 404) {
          if (target.key === KEY) removeActiveMarker = true;
          else if (owner && target.value!.owner === owner) localStorage.removeItem(target.key);
          continue;
        }
        failure ||= error;
      }
    }
    if (getSessionRevision() !== revision) return;
    if (otherOwner) { if (failure) throw failure; return; }
    if (localStorage.getItem(KEY) !== raw) return;
    const { subscription } = await currentSubscription(); check(revision);
    if (localStorage.getItem(KEY) !== raw) return;
    try { if (subscription && !await subscription.unsubscribe()) throw new Error("Device alert removal could not be confirmed."); }
    catch (error) {
      if (getSessionRevision() === revision && marker && localStorage.getItem(KEY) === raw) localStorage.setItem(KEY, JSON.stringify({ ...marker, pending: true }));
      throw error;
    }
    check(revision);
    if (failure && marker && localStorage.getItem(KEY) === raw) localStorage.setItem(KEY, JSON.stringify({ ...marker, pending: true }));
    if (!failure && removeActiveMarker && localStorage.getItem(KEY) === raw) localStorage.removeItem(KEY);
    check(revision);
    if (failure) throw failure;
  });
}
export function listenForPush(onOpen: (id: string) => void, onUpdate: () => void) {
  const callback = (event: MessageEvent) => {
    if (event.data?.type === "open-listing" && typeof event.data.listing_id === "string") onOpen(event.data.listing_id);
    if (event.data?.type === "alerts-updated") onUpdate();
  };
  navigator.serviceWorker?.addEventListener("message", callback);
  return () => navigator.serviceWorker?.removeEventListener("message", callback);
}
