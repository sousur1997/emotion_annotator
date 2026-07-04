// Bump CACHE whenever app.js / index.html / style.css change, so old
// clients pick up the new files instead of serving a stale cached copy.
const CACHE = 'emotion-annotator-v12';
const ASSETS = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './manifest.json',
  './icon.svg',
  './EmotionWheel_PNG.png'
];

self.addEventListener('install', e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
  );
  self.clients.claim();
});

// Network-first: always try to fetch the latest version when online, and
// only fall back to the cached copy if the network request fails (offline).
// This is what makes the "standalone app" actually pick up updates instead
// of being frozen at whatever was cached on first install.
self.addEventListener('fetch', e=>{
  if(e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request).then(res=>{
      const clone = res.clone();
      caches.open(CACHE).then(c=>c.put(e.request, clone));
      return res;
    }).catch(()=> caches.match(e.request))
  );
});
