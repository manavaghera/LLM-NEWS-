import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { alerts, useAlerts } from '@/lib/alerts'
import { formatShortDate } from '@/lib/format'
import { MAX_FOLLOWED_STORIES, useLibrary } from '@/lib/library'

/** Followed topics are checked on every page, including when the front page is not open. */
export function AlertsMenu() {
  const client = useQueryClient()
  const library = useLibrary()
  const data = useAlerts()
  const [open, setOpen] = useState(false)
  const [browserAlerts, setBrowserAlerts] = useState(() => typeof Notification !== 'undefined' && Notification.permission === 'granted')
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
    if (typeof Notification === 'undefined') return
    const permission = await Notification.requestPermission()
    setBrowserAlerts(permission === 'granted')
    if (permission === 'granted') void api.analytics('alert_enabled').catch(() => undefined)
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
          <p className="mb-3 text-xs text-muted">New matches for your topics, later coverage and changes to stories you follow. Alerts stay in this browser.</p>
          {!browserAlerts && typeof Notification !== 'undefined' && Notification.permission !== 'denied' && <button type="button" onClick={() => { void enableBrowserAlerts() }} className="mb-3 rounded-full border border-rule px-3 py-1.5 text-xs font-medium hover:bg-sunken">Enable browser notifications</button>}
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
