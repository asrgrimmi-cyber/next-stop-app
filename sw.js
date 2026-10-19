// Next Stop service worker: only shows last-call notifications and routes their clicks back to the app.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const fid = (e.notification.data || {}).fid;
  const type = e.action === 'board' ? 'board' : 'open';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    const c = list[0];
    if (c) { c.postMessage({ type, fid }); return c.focus(); }
    return self.clients.openWindow('/');
  }));
});
