import { useSyncExternalStore } from 'react'
import type { NewsItem } from '@/api/types'
import { storage } from './utils'

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
}

const KEY = 'newssense-library'
const MAX_SAVED = 300
const EMPTY: Library = { saved: [], categories: [], keywords: [] }

const strings = (value: unknown) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [])

export function parseLibrary(raw: string | null): Library {
  try {
    const data = JSON.parse(raw ?? 'null')
    if (!data || typeof data !== 'object') return EMPTY
    const saved = Array.isArray(data.saved)
      ? data.saved.filter((s: SavedArticle) => s && typeof s.date === 'string' && typeof s.group_id === 'string' && typeof s.headline === 'string')
      : []
    return { saved, categories: strings(data.categories), keywords: strings(data.keywords) }
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

export function toggleIn(list: string[], value: string): string[] {
  const v = value.trim().toLowerCase()
  if (!v) return list
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v]
}

/** Does a story match something the reader follows? */
export function matchesFollows(item: NewsItem, lib: Library): boolean {
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
  isSaved: (lib: Library, date: string, groupId: string) => lib.saved.some((s) => s.date === date && s.group_id === groupId),
  toggleSaved: (article: Omit<SavedArticle, 'saved_at'>) => commit(toggleSaved(state, article)),
  toggleCategory: (category: string) => commit({ ...state, categories: toggleIn(state.categories, category) }),
  toggleKeyword: (keyword: string) => commit({ ...state, keywords: toggleIn(state.keywords, keyword) }),
}
