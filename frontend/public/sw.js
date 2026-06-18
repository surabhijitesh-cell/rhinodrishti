/* Rhino Drishti — Service Worker: push handler + notification click deep-link routing */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_) {}

  const title = data.title || "Rhino Drishti";
  const options = {
    body: data.body || "",
    icon: data.icon || "/icon-192.png",
    badge: data.badge || "/badge-72.png",
    data: {
      deep_link: data.deep_link || "/",
      notification_id: data.notification_id || "",
    },
    tag: data.notification_id || "rd-notification",
    renotify: false,
    requireInteraction: true,   // stays in drawer until user taps/dismisses
    silent: false,              // play default system sound
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const deepLink = event.notification.data?.deep_link || "/";
  const targetUrl = self.location.origin + deepLink;

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((wins) => {
        // Focus existing app tab if open
        const appWin = wins.find((w) =>
          w.url.startsWith(self.location.origin)
        );
        if (appWin) {
          appWin.focus();
          return appWin.navigate(targetUrl);
        }
        // Otherwise open a new tab
        return clients.openWindow(targetUrl);
      })
  );
});
