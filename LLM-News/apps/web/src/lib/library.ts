import { useSyncExternalStore } from 'react'
import type { NewsItem } from '@/api/types'
import { storage } from './utils'
import { importLibrary } from './libraryTransfer'

// The reader's saved articles and followed topics. Kept only in this browser (no accounts).

export interface SavedArticle {
  date: string
  group_id: string
  headline: string
  category: string
  image_url?: string
  saved_at: number
}

export interface Library {
  saved: SavedArticle[]
  categories: string[]
  keywords: string[]
  stories: FollowedStory[]
}

export interface FollowedStory {
  date: string
  group_id: string
  headline: string
  category: string
  followed_at: number
  content_version?: string
  story_identity?: string
}

export const MAX_FOLLOWED_STORIES = 20

const KEY = 'newssense-library'
const MAX_SAVED = 300
const EMPTY: Library = { saved: [], categories: [], keywords: [], stories: [] }

const strings = (value: unknown) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [])

export function parseLibrary(raw: string | null): Library {
  try {
    const data = JSON.parse(raw ?? 'null')
    if (!data || typeof data !== 'object') return EMPTY
    const saved = Array.isArray(data.saved)
      ? data.saved.filter((s: SavedArticle) => s && typeof s.date === 'string' && typeof s.group_id === 'string' && typeof s.headline === 'string')
      : []
    const stories = Array.isArray(data.stories) ? data.stories.filter((s: FollowedStory) => s
      && typeof s.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s.date)
      && typeof s.group_id === 'string' && /^group_\d+$/.test(s.group_id)
      && typeof s.headline === 'string' && typeof s.category === 'string'
      && typeof s.followed_at === 'number' && Number.isFinite(s.followed_at)
      && (s.content_version === undefined || typeof s.content_version === 'string')
      && (s.story_identity === undefined || typeof s.story_identity === 'string')).slice(0, MAX_FOLLOWED_STORIES) : []
    return { saved, categories: strings(data.categories), keywords: strings(data.keywords), stories }
  } catch {
    return EMPTY
  }
}

const sameArticle = (a: { date: string; group_id: string }, b: { date: string; group_id: string }) =>
  a.date === b.date && a.group_id === b.group_id

export function toggleSaved(lib: Library, article: Omit<SavedArticle, 'saved_at'>, now = Date.now()): Library {
  const exists = lib.saved.some((s) => sameArticle(s, article))
  const saved = exists
    ? lib.saved.filter((s) => !sameArticle(s, article))
    : [{ ...article, saved_at: now }, ...lib.saved].slice(0, MAX_SAVED)
  return { ...lib, saved }
}

export function toggleFollowedStory(lib: Library, story: Omit<FollowedStory, 'followed_at'>, now = Date.now()): Library {
  const existing = lib.stories.find((s) => sameArticle(s, story))
  const replacement = existing?.story_identity && story.story_identity && existing.story_identity !== story.story_identity
  const rest = lib.stories.filter((s) => !sameArticle(s, story))
  if (existing && !replacement) return { ...lib, stories: rest }
  if (!existing && lib.stories.length >= MAX_FOLLOWED_STORIES) throw new Error(`You can follow up to ${MAX_FOLLOWED_STORIES} stories. Remove one from Saved first.`)
  return { ...lib, stories: [{ ...story, followed_at: now }, ...rest] }
}

export function toggleIn(list: string[], value: string): string[] {
  const v = value.trim().toLowerCase()
  if (!v) return list
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v]
}

/** Does a story match something the reader follows? */
export function matchesFollows(item: NewsItem, lib: Pick<Library, 'categories' | 'keywords'>): boolean {
  if (lib.categories.includes(item.category.toLowerCase())) return true
  if (!lib.keywords.length) return false
  const text = `${item.headline} ${item.subheadline ?? ''} ${item.summary}`.toLowerCase()
  return lib.keywords.some((keyword) => text.includes(keyword))
}

// --- store shared by every component, persisted in localStorage ---
let state: Library = parseLibrary(storage.get(KEY))
const listeners = new Set<() => void>()

function commit(next: Library) {
  state = next
  storage.set(KEY, JSON.stringify(next))
  listeners.forEach((listener) => listener())
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === KEY) {
      state = parseLibrary(event.newValue)
      listeners.forEach((listener) => listener())
    }
  })
}

const subscribe = (listener: () => void) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useLibrary(): Library {
  return useSyncExternalStore(subscribe, () => state, () => EMPTY)
}

export const library = {
  import: (raw: string) => commit(importLibrary(raw, state)),
  isSaved: (lib: Library, date: string, groupId: string) => lib.saved.some((s) => s.date === date && s.group_id === groupId),
  toggleSaved: (article: Omit<SavedArticle, 'saved_at'>) => commit(toggleSaved(state, article)),
  toggleCategory: (category: string) => commit({ ...state, categories: toggleIn(state.categories, category) }),
  toggleKeyword: (keyword: string) => commit({ ...state, keywords: toggleIn(state.keywords, keyword) }),
  toggleStory: (story: Omit<FollowedStory, 'followed_at'>) => commit(toggleFollowedStory(state, story)),
}
