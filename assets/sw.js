var CACHE_NAME = "face-tracker-v1";

var LOCAL_ASSETS = [
  "/",
  "/index.html",
  "/app.js",
  "/style.css",
  "/libs/socket.io.min.js",
  "/img/icon-reset.svg",
  "/qualcomm-logo.png"
];

var CDN_PATTERNS = [
  "cdn.jsdelivr.net/npm/@mediapipe",
  "storage.googleapis.com/mediapipe-models"
];

function isCDNRequest(url) {
  for (var i = 0; i < CDN_PATTERNS.length; i++) {
    if (url.indexOf(CDN_PATTERNS[i]) !== -1) return true;
  }
  return false;
}

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(LOCAL_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names.filter(function (n) { return n !== CACHE_NAME; })
             .map(function (n) { return caches.delete(n); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  if (event.request.method !== "GET") return;

  var url = event.request.url;

  if (isCDNRequest(url)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(function (cache) {
        return cache.match(event.request).then(function (cached) {
          if (cached) return cached;
          return fetch(event.request).then(function (response) {
            if (response.ok) {
              cache.put(event.request, response.clone());
            }
            return response;
          });
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(function (cached) {
      return cached || fetch(event.request);
    })
  );
});
