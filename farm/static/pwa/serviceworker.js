// Miginon Farm service worker.
//
// Network-first: this is a live farm records app, so a page should always
// show fresh data when the device is online. The cache only exists to make
// the app shell (icons + the offline page) available when there's no
// connection at all - it deliberately does not cache farm data pages.
var CACHE_NAME = 'miginon-farm-v3';
var FILES_TO_CACHE = [
    '/offline/',
    '/static/images/icons/icon-192x192.png',
    '/static/images/icons/icon-512x512.png',
    '/static/images/icons/icon-512x512-maskable.png',
    '/static/images/icons/apple-icon-180.png',
    '/static/images/icons/splash-640x1136.png',
    '/static/images/icons/splash-750x1334.png',
    '/static/images/icons/splash-1242x2208.png',
    '/static/images/icons/splash-1125x2436.png',
    '/static/images/icons/splash-828x1792.png',
    '/static/images/icons/splash-1242x2688.png',
    '/static/images/icons/splash-1536x2048.png',
    '/static/images/icons/splash-1668x2224.png',
    '/static/images/icons/splash-1668x2388.png',
    '/static/images/icons/splash-2048x2732.png',
];

self.addEventListener('install', function (event) {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(FILES_TO_CACHE);
        })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(
                cacheNames
                    .filter(function (name) { return name.startsWith('miginon-farm-') && name !== CACHE_NAME; })
                    .map(function (name) { return caches.delete(name); })
            );
        }).then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request).catch(function () {
            return caches.match(event.request).then(function (cached) {
                return cached || caches.match('/offline/');
            });
        })
    );
});

// Device push notifications (see notifications/push.py for the send side).
// The payload is the JSON string notify() builds: {title, body, url}.
self.addEventListener('push', function (event) {
    var data = { title: 'Miginon Farm', body: 'You have a new notification.', url: '/notifications/' };
    if (event.data) {
        try { data = Object.assign(data, event.data.json()); } catch (e) { /* keep defaults */ }
    }
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/images/icons/icon-192x192.png',
            badge: '/static/images/icons/icon-192x192.png',
            data: { url: data.url },
        })
    );
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/notifications/';
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clients) {
            for (var i = 0; i < clients.length; i++) {
                if (clients[i].url.indexOf(url) !== -1 && 'focus' in clients[i]) return clients[i].focus();
            }
            if (self.clients.openWindow) return self.clients.openWindow(url);
        })
    );
});
