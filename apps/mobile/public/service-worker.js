// Push only: never caches private API responses or authentication data.
self.addEventListener("push", (event) => {
  let payload;
  try {
    payload = event.data.json();
  } catch {
    return;
  }
  if (
    typeof payload.listing_id !== "string" ||
    typeof payload.notification_id !== "string"
  )
    return;
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(payload.title || "Rental alert", {
        body: payload.body,
        tag: payload.notification_id,
        renotify: false,
        data: {
          listing_id: payload.listing_id,
          url: "/?listing=" + encodeURIComponent(payload.listing_id),
        },
      }),
      self.clients
        .matchAll({ type: "window", includeUncontrolled: true })
        .then((clients) => {
          for (const client of clients)
            client.postMessage({ type: "alerts-updated" });
        }),
    ]),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data;
  if (typeof data?.listing_id !== "string") return;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then(async (clients) => {
        const client = clients.find(
          (client) => new URL(client.url).origin === self.location.origin,
        );
        if (client) {
          await client.focus();
          client.postMessage({
            type: "open-listing",
            listing_id: data.listing_id,
          });
        } else
          await self.clients.openWindow(
            "/?listing=" + encodeURIComponent(data.listing_id),
          );
      }),
  );
});
