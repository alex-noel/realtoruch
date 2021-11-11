import { request } from "./api";
const KEY = "realtoruch.push.v1";
export async function pushEnabled() {
  return !!localStorage.getItem(KEY);
}
export async function enablePush() {
  if (
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  )
    throw new Error(
      "This browser does not support push notifications. Your in-app inbox still works.",
    );
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw new Error(
      "Allow notifications in your browser settings to enable alerts.",
    );
  const config = await request<{
    web_push_enabled: boolean;
    vapid_public_key: string;
  }>("/v1/notifications/config");
  if (!config.web_push_enabled)
    throw new Error(
      "Browser push is not configured yet. Your alerts are saved in the inbox.",
    );
  await navigator.serviceWorker.register("/service-worker.js");
  const registration = await navigator.serviceWorker.ready;
  const raw = atob(
    config.vapid_public_key.replace(/-/g, "+").replace(/_/g, "/"),
  );
  const key = Uint8Array.from(raw, (c) => c.charCodeAt(0));
  const subscription =
    (await registration.pushManager.getSubscription()) ||
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: key,
    }));
  const json = subscription.toJSON();
  const result = await request<{ id: string }>("/v1/me/push-subscriptions", {
    method: "POST",
    body: JSON.stringify({
      kind: "web",
      endpoint: json.endpoint,
      keys: json.keys,
    }),
  });
  localStorage.setItem(KEY, result.id);
}
export async function disablePush() {
  const id = localStorage.getItem(KEY);
  try {
    if (id)
      await request(`/v1/me/push-subscriptions/${id}`, { method: "DELETE" });
  } finally {
    // Local revocation must still happen if the account session has expired.
    const registration = await navigator.serviceWorker?.getRegistration();
    const subscription = await registration?.pushManager.getSubscription();
    await subscription?.unsubscribe();
    localStorage.removeItem(KEY);
  }
}
export function listenForPush(
  onOpen: (id: string) => void,
  onUpdate: () => void,
) {
  const callback = (event: MessageEvent) => {
    if (
      event.data?.type === "open-listing" &&
      typeof event.data.listing_id === "string"
    )
      onOpen(event.data.listing_id);
    if (event.data?.type === "alerts-updated") onUpdate();
  };
  navigator.serviceWorker?.addEventListener("message", callback);
  return () =>
    navigator.serviceWorker?.removeEventListener("message", callback);
}
