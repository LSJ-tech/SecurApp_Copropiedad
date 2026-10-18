const CACHE_NAME = "mibarrio-plus-v1";
const OFFLINE_URL = "/offline/";

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        ))
    );
    self.clients.claim();
});

// Red primero, con una página de respaldo si no hay conexión -- el contenido
// (alertas, avisos) cambia seguido, así que nunca conviene mostrar una
// versión vieja desde el cache en vez de intentar la red.
self.addEventListener("fetch", (event) => {
    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(OFFLINE_URL))
        );
    }
});

self.addEventListener("push", (event) => {
    let datos = {};
    try {
        datos = event.data ? event.data.json() : {};
    } catch (error) {
        datos = { title: "Mi Barrio+", body: event.data ? event.data.text() : "" };
    }
    const opciones = {
        body: datos.body || "",
        icon: "/static/core/icon-192.png",
        badge: "/static/core/icon-192.png",
        data: datos.data || {},
        requireInteraction: datos.data?.tipo === "alerta",
    };
    event.waitUntil(self.registration.showNotification(datos.title || "Mi Barrio+", opciones));
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((lista) => {
            for (const cliente of lista) {
                if ("focus" in cliente) return cliente.focus();
            }
            return clients.openWindow("/");
        })
    );
});
