import { useSyncExternalStore } from 'react'
import type { NewsItem, StoryUpdates } from '@/api/types'
import { matchesFollows, type FollowedStory, type Library } from './library'
import { storage } from './utils'

export interface StoryAlert {
  key: string
  date: string
  group_id: string
  headline: string
  category: string
  read: boolean
  kind?: 'coverage' | 'updated'
}

export interface Alerts { items: StoryAlert[]; seen: string[]; versions?: Record<string, string>; unavailable?: string[] }
const KEY = 'newssense-alerts'
const EMPTY: Alerts = { items: [], seen: [] }

export function parseAlerts(raw: string | null): Alerts {
  try {
    const data = JSON.parse(raw ?? 'null')
    if (!data || !Array.isArray(data.items) || !Array.isArray(data.seen)) return EMPTY
    const items = data.items.filter((item: StoryAlert) => item && typeof item.key === 'string'
      && typeof item.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(item.date)
      && typeof item.group_id === 'string' && /^group_\d+$/.test(item.group_id)
      && typeof item.headline === 'string' && typeof item.category === 'string' && typeof item.read === 'boolean').slice(0, 100)
    const versions = data.versions && typeof data.versions === 'object' ? Object.fromEntries(Object.entries(data.versions).filter(([, v]) => typeof v === 'string').slice(-1000)) as Record<string, string> : undefined
    const unavailable = Array.isArray(data.unavailable) ? data.unavailable.filter((s: unknown) => typeof s === 'string').slice(-200) : undefined
    return { items, seen: data.seen.filter((id: unknown) => typeof id === 'string').slice(-3000), ...(versions ? { versions } : {}), ...(unavailable ? { unavailable } : {}) }
  } catch { return EMPTY }
}

const storyKey = (story: { date: string; group_id: string; story_identity?: string }) => `${story.date}/${story.group_id}${story.story_identity ? `:${story.story_identity}` : ''}`

export function discoverAlerts(state: Alerts, stories: NewsItem[], library: Pick<Library, 'categories' | 'keywords'>): Alerts {
  const seen = new Set(state.seen)
  const added: StoryAlert[] = []
  for (const story of stories) {
    const key = storyKey(story)
    if (seen.has(key) || !matchesFollows(story, library)) continue
    seen.add(key)
    added.push({ key, date: story.date, group_id: story.group_id, headline: story.headline, category: story.category, read: false })
  }
  return added.length ? { ...state, items: [...added, ...state.items].slice(0, 100), seen: [...seen].slice(-3000) } : state
}

export function unavailableStory(state: Alerts, story: Pick<FollowedStory, 'date' | 'group_id'>): Alerts {
  const key = `${story.date}/${story.group_id}`
  return state.unavailable?.includes(key) ? state : { ...state, unavailable: [...(state.unavailable ?? []), key].slice(-200) }
}

/** A follow is anchored to the original story, even when a dated group ID is later reused. */
export function discoverStoryAlerts(state: Alerts, followed: FollowedStory, response: StoryUpdates): Alerts {
  if (!followed.story_identity || followed.story_identity !== response.story_identity) return unavailableStory(state, followed)
  const anchor = storyKey(followed)
  const checkpoint = `follow:${anchor}:${followed.followed_at}`
  const versions = { ...state.versions }
  const seen = new Set(state.seen)
  const added: StoryAlert[] = []
  let changed = false
  const add = (story: { date: string; group_id: string; headline: string; category: string }, key: string, kind: 'coverage' | 'updated') => {
    if (!seen.has(key)) {
      added.push({ key, date: story.date, group_id: story.group_id, headline: story.headline, category: story.category, read: false, kind })
      seen.add(key)
    }
  }
  const baseline = versions[checkpoint] ?? followed.content_version ?? response.content_version
  if (baseline !== response.content_version) add(followed, `${anchor}@${response.content_version}`, 'updated')
  if (versions[checkpoint] !== response.content_version) { versions[checkpoint] = response.content_version; changed = true }
  for (const story of response.updates) {
    if (!story.content_version) continue
    const key = storyKey(story)
    const previous = versions[key]
    if (previous === story.content_version) continue
    // A topic alert may already have introduced this story; do not introduce it twice.
    if (previous || !seen.has(key)) add(story, `${key}@${story.content_version}`, previous ? 'updated' : 'coverage')
    seen.add(key)
    versions[key] = story.content_version
    changed = true
  }
  const unavailable = state.unavailable?.filter((key) => key !== `${followed.date}/${followed.group_id}`)
  if (unavailable?.length !== state.unavailable?.length) changed = true
  return changed || added.length ? { ...state, items: [...added, ...state.items].slice(0, 100), seen: [...seen].slice(-3000),
    versions: Object.fromEntries(Object.entries(versions).slice(-1000)), ...(unavailable ? { unavailable } : {}) } : state
}

let state = parseAlerts(storage.get(KEY))
const listeners = new Set<() => void>()
function commit(next: Alerts) {
  if (next === state) return
  state = next
  storage.set(KEY, JSON.stringify(state))
  listeners.forEach((listener) => listener())
}
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === KEY) {
      state = parseAlerts(event.newValue)
      listeners.forEach((listener) => listener())
    }
  })
}
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } }
export function useAlerts() { return useSyncExternalStore(subscribe, () => state, () => EMPTY) }
export const alerts = {
  discover: (stories: NewsItem[], library: Pick<Library, 'categories' | 'keywords'>) => commit(discoverAlerts(state, stories, library)),
  discoverStory: (story: FollowedStory, response: StoryUpdates) => commit(discoverStoryAlerts(state, story, response)),
  unavailable: (story: FollowedStory) => commit(unavailableStory(state, story)),
  markRead: (key?: string) => commit({ ...state, items: state.items.map((item) => !key || item.key === key ? { ...item, read: true } : item) }),
}
