import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { alerts, useAlerts } from '@/lib/alerts'
import { formatShortDate } from '@/lib/format'
import { MAX_FOLLOWED_STORIES, useLibrary } from '@/lib/library'
import { storage } from '@/lib/utils'

const PUSH_KEY = 'newssense-push-management'

function applicationKey(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.padEnd(value.length + (4 - value.length % 4) % 4, '=')
  const bytes = atob(padded.replaceAll('-', '+').replaceAll('_', '/'))
  return Uint8Array.from(bytes, (character) => character.charCodeAt(0))
}

function pushPayload(subscription: PushSubscription) {
  const json = subscription.toJSON()
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) throw new Error('Browser push subscription is incomplete.')
  return { endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } }
}

/** Followed topics are checked on every page, including when the front page is not open. */
export function AlertsMenu() {
  const client = useQueryClient()
  const library = useLibrary()
  const data = useAlerts()
  const [open, setOpen] = useState(false)
  const [browserAlerts, setBrowserAlerts] = useState(() => typeof Notification !== 'undefined' && Notification.permission === 'granted')
  const [pushEnabled, setPushEnabled] = useState(() => !!storage.get(PUSH_KEY))
  const [pushError, setPushError] = useState('')
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 3_600_000 })
  const following = library.categories.length + library.keywords.length > 0
  const dates = useQuery({ queryKey: ['dates'], queryFn: api.dates, enabled: following, refetchInterval: following ? 60_000 : false })
  const date = dates.data?.dates[0]
  const news = useQuery({ queryKey: ['news', date], queryFn: () => api.news(date!), enabled: following && !!date,
    refetchInterval: following ? 60_000 : false })
  useEffect(() => {
    if (news.data) alerts.discover(news.data, library)
  }, [news.data, library])
  const storyUpdates = useQueries({ queries: library.stories.slice(0, MAX_FOLLOWED_STORIES).map((story) => ({
    queryKey: ['story-updates', story.date, story.group_id, story.story_identity],
    queryFn: () => api.storyUpdates(story.date, story.group_id), refetchInterval: 120_000, staleTime: 60_000,
  })) })
  useEffect(() => {
    storyUpdates.forEach((query, index) => {
      const story = library.stories[index]
      if (query.data) alerts.discoverStory(story, query.data)
      else if (query.error instanceof ApiError && query.error.status === 404) alerts.unavailable(story)
    })
  }, [storyUpdates, library.stories])
  const unread = data.items.filter((item) => !item.read).length
  const previousUnread = useRef(unread)
  useEffect(() => {
    if (browserAlerts && unread > previousUnread.current && data.items[0] && document.visibilityState !== 'visible') {
      new Notification('NewsSense update', { body: data.items[0].headline, tag: data.items[0].key })
    }
    previousUnread.current = unread
  }, [browserAlerts, data.items, unread])
  const enableBrowserAlerts = async () => {
    try {
      setPushError('')
      if (typeof Notification === 'undefined' || !('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error('Push notifications are not supported in this browser.')
      if (!following) throw new Error('Follow a category or keyword before enabling push alerts.')
      if (!config.data?.vapid_public_key) throw new Error('Push notifications are not configured yet.')
      const permission = await Notification.requestPermission()
      setBrowserAlerts(permission === 'granted')
      if (permission !== 'granted') return
      const registration = await navigator.serviceWorker.register('/sw.js')
      const subscription = await registration.pushManager.getSubscription() ?? await registration.pushManager.subscribe({
        userVisibleOnly: true, applicationServerKey: applicationKey(config.data.vapid_public_key),
      })
      const saved = await api.pushSubscribe(pushPayload(subscription), library.categories, library.keywords)
      storage.set(PUSH_KEY, JSON.stringify({ endpoint: subscription.endpoint, token: saved.management_token }))
      setPushEnabled(true)
      void api.analytics('alert_enabled').catch(() => undefined)
    } catch (error) {
      setPushError(error instanceof Error ? error.message : 'Could not enable push notifications.')
    }
  }

  useEffect(() => {
    if (!pushEnabled || !following || !('serviceWorker' in navigator)) return
    void navigator.serviceWorker.ready.then(async (registration) => {
      const subscription = await registration.pushManager.getSubscription()
      if (!subscription) return
      const current = JSON.parse(storage.get(PUSH_KEY) ?? 'null') as { token?: string } | null
      const saved = await api.pushSubscribe(pushPayload(subscription), library.categories, library.keywords, current?.token)
      storage.set(PUSH_KEY, JSON.stringify({ endpoint: subscription.endpoint, token: saved.management_token }))
    }).catch(() => undefined)
  }, [pushEnabled, following, library.categories, library.keywords])

  const disablePushAlerts = async () => {
    try {
      if (!('serviceWorker' in navigator)) return
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      const saved = JSON.parse(storage.get(PUSH_KEY) ?? 'null') as { endpoint?: string; token?: string } | null
      if (saved?.endpoint && saved.token) await api.pushUnsubscribe(saved.endpoint, saved.token).catch(() => undefined)
      if (subscription) await subscription.unsubscribe()
      storage.remove(PUSH_KEY)
      setPushEnabled(false)
      setPushError('')
    } catch (error) {
      setPushError(error instanceof Error ? error.message : 'Could not disable push notifications.')
    }
  }

  return (
    <div className="relative">
      <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="story-alerts"
        aria-label={unread ? `Alerts, ${unread} unread` : 'Alerts'} className="relative">
        <Bell />
        {unread > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-accent px-1 text-[10px] text-accent-ink">{unread}</span>}
      </Button>
      {open && (
        <section id="story-alerts" aria-label="Story alerts" className="fixed top-16 right-4 z-40 max-h-[70dvh] w-[min(360px,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-rule bg-surface p-4 shadow-xl sm:absolute sm:top-12 sm:right-0">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-semibold">Story alerts</h2>
            <Button size="icon" variant="ghost" onClick={() => setOpen(false)} aria-label="Close alerts"><X /></Button>
          </div>
          <p className="mb-3 text-xs text-muted">New matches for your topics, later coverage and changes to stories you follow. Push alerts can arrive while this site is closed.</p>
          {!pushEnabled && typeof Notification !== 'undefined' && Notification.permission !== 'denied' && <button type="button" onClick={() => { void enableBrowserAlerts() }} className="mb-3 rounded-full border border-rule px-3 py-1.5 text-xs font-medium hover:bg-sunken">Enable push notifications</button>}
          {pushEnabled && <button type="button" onClick={() => { void disablePushAlerts() }} className="mb-3 rounded-full border border-rule px-3 py-1.5 text-xs font-medium hover:bg-sunken">Disable push notifications</button>}
          {pushError && <p role="alert" className="mb-3 text-xs text-negative">{pushError}</p>}
          {(news.error || dates.error || storyUpdates.some((query) => query.error)) && <p role="status" className="mb-3 text-xs text-negative">Couldn&apos;t check some stories. We&apos;ll try again shortly.</p>}
          {unread > 0 && <button type="button" onClick={() => alerts.markRead()} className="mb-3 text-sm text-accent hover:underline">Mark all read</button>}
          {data.items.length ? (
            <ul className="divide-y divide-rule">
              {data.items.map((item) => (
                <li key={item.key} className="py-3">
                  <Link to={`/article/${item.date}/${item.group_id}`} onClick={() => {
                    if (item.kind === 'updated') {
                      void client.invalidateQueries({ queryKey: ['article', item.date, item.group_id] })
                      void client.invalidateQueries({ queryKey: ['corrections', item.date, item.group_id] })
                    }
                    alerts.markRead(item.key); setOpen(false)
                  }}
                    className={`block text-sm leading-snug hover:text-accent ${item.read ? 'text-muted' : 'font-semibold'}`}>
                    {!item.read && <span className="mr-1 text-accent" aria-label="Unread">●</span>}{item.headline}
                  </Link>
                  <p className="mt-1 text-xs text-faint">{formatShortDate(item.date)}</p>
                  {item.kind && <p className="mt-1 text-xs text-accent">{item.kind === 'coverage' ? 'Later coverage of a story you follow' : 'Article text or correction updated'}</p>}
                </li>
              ))}
            </ul>
          ) : <p className="py-3 text-sm text-muted">No matches yet. Follow a story, category or search word to get alerts here.</p>}
          <Link to="/saved" onClick={() => setOpen(false)} className="mt-3 block text-sm text-accent hover:underline">Manage followed stories & topics →</Link>
        </section>
      )}
    </div>
  )
}
