/* Service Worker:離線頁 + 靜態資源快取
 * 更新快取內容時,請調高 VERSION。
 * Gradio 本身的 API / 佇列 / 檔案請求不會被快取,資料永遠即時。 */
const VERSION = "v1";
const CACHE = "csv-viewer-" + VERSION;
const OFFLINE_URL = "/pwa/offline.html";
const PRECACHE = [
  OFFLINE_URL,
  "/pwa/icons/icon-192.png",
  "/pwa/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // 頁面導覽:優先走網路,離線時顯示離線頁
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  // /pwa/ 底下的靜態資源:快取優先
  if (url.pathname.startsWith("/pwa/")) {
    event.respondWith(
      caches.match(req).then((hit) =>
        hit ||
        fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
      )
    );
  }
  // 其餘請求(Gradio API 等)交給瀏覽器預設處理
});
