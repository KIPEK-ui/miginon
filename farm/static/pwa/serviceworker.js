// FarmIQ service worker.
//
// Network-first: this is a live farm records app, so a page should always
// show fresh data when the device is online. The cache only exists to make
// the app shell (icons + the offline page) available when there's no
// connection at all - it deliberately does not cache farm data pages.
var CACHE_NAME = 'farmiq-v1';
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
                    .filter(function (name) {
                        return (name.startsWith('farmiq-') || name.startsWith('miginon-farm-')) && name !== CACHE_NAME;
                    })
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
    var data = { title: 'FarmIQ', body: 'You have a new notification.', url: '/notifications/' };
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

// Offline data-entry queue (see static/js/offline-queue.js for the primary
// page-side flush, triggered on the 'online' event - this is the bonus path
// for browsers that support Background Sync (Chrome/Android) so a queued
// record can still flush even if the tab was closed while offline. Reads
// the same IndexedDB database/store the page writes to. Deliberately
// duplicated rather than shared via importScripts: it's a handful of lines,
// and a service worker can't access document.cookie for a CSRF header
// anyway - it doesn't need to, since the queued fields already include the
// form's own csrfmiddlewaretoken hidden input.
var OFFLINE_DB_NAME = 'farmiq-offline-queue';
var OFFLINE_STORE_NAME = 'pending-records';

function openOfflineDb() {
    return new Promise(function (resolve, reject) {
        var request = indexedDB.open(OFFLINE_DB_NAME, 1);
        request.onupgradeneeded = function () {
            if (!request.result.objectStoreNames.contains(OFFLINE_STORE_NAME)) {
                request.result.createObjectStore(OFFLINE_STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = function () { reject(request.error); };
    });
}

function flushOfflineQueue() {
    return openOfflineDb().then(function (db) {
        return new Promise(function (resolve, reject) {
            var tx = db.transaction(OFFLINE_STORE_NAME, 'readonly');
            var req = tx.objectStore(OFFLINE_STORE_NAME).getAll();
            req.onsuccess = function () { resolve(req.result); };
            req.onerror = function () { reject(req.error); };
        });
    }).then(function (records) {
        return records.reduce(function (chain, record) {
            return chain.then(function () {
                var body = new URLSearchParams();
                record.fields.forEach(function (pair) { body.append(pair[0], pair[1]); });
                return fetch(record.url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body.toString(),
                    credentials: 'same-origin',
                }).then(function (response) {
                    if (!response.redirected) return; // leave it for the page-side flush to retry/give up on
                    return openOfflineDb().then(function (db) {
                        return new Promise(function (resolve, reject) {
                            var tx = db.transaction(OFFLINE_STORE_NAME, 'readwrite');
                            tx.objectStore(OFFLINE_STORE_NAME).delete(record.id);
                            tx.oncomplete = resolve;
                            tx.onerror = function () { reject(tx.error); };
                        });
                    });
                }, function () { /* still offline - leave queued */ });
            });
        }, Promise.resolve());
    });
}

self.addEventListener('sync', function (event) {
    if (event.tag !== 'farmiq-offline-queue') return;
    event.waitUntil(flushOfflineQueue());
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
