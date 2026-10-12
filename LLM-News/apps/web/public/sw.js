self.addEventListener('push', (event) => {
  let payload = { title: 'NewsSense update', body: 'New coverage is available.', url: '/', tag: 'newssense-update' }
  try { payload = { ...payload, ...event.data.json() } } catch { /* use the safe fallback */ }
  event.waitUntil(self.registration.showNotification(payload.title, {
    body: payload.body,
    tag: payload.tag,
    icon: '/favicon.svg',
    data: { url: payload.url },
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/', self.location.origin).href
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
    const existing = windows.find((client) => client.url === target)
    return existing ? existing.focus() : clients.openWindow(target)
  }))
})
