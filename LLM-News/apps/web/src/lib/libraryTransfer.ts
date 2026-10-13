import { MAX_FOLLOWED_STORIES, type FollowedStory, type Library, type SavedArticle } from './library'

export const MAX_IMPORT_BYTES = 2 * 1024 * 1024

export function exportLibrary(library: Library): string {
  return JSON.stringify({ version: 1, ...library }, null, 2)
}

function topics(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > 500 || value.some((v) => typeof v !== 'string' || !v.trim() || v.length > 100)) {
    throw new Error('Topics must be a list of short, non-empty words or categories.')
  }
  return [...new Set(value.map((v: string) => v.trim().toLowerCase()))]
}

function article(value: unknown): SavedArticle {
  if (!value || typeof value !== 'object') throw new Error('A saved story is invalid.')
  const s = value as Record<string, unknown>
  const valid = typeof s.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s.date)
    && Number.isFinite(Date.parse(`${s.date}T00:00:00Z`)) && new Date(`${s.date}T00:00:00Z`).toISOString().slice(0, 10) === s.date
    && typeof s.group_id === 'string' && s.group_id.length <= 50 && /^group_\d+$/.test(s.group_id)
    && typeof s.headline === 'string' && !!s.headline.trim() && s.headline.length <= 1000
    && typeof s.category === 'string' && !!s.category.trim() && s.category.length <= 100
    && typeof s.saved_at === 'number' && Number.isFinite(s.saved_at) && s.saved_at >= 0 && s.saved_at <= 8.64e15
  if (!valid) throw new Error('A saved story has missing or invalid fields.')
  let image: string | undefined
  if (s.image_url !== undefined) {
    if (typeof s.image_url !== 'string' || s.image_url.length > 2048) throw new Error('A saved story has an invalid image URL.')
    // Library backups cannot introduce remote image requests or executable URLs.
    if (s.image_url && (!/^\/static\/images\/[\w./-]+$/.test(s.image_url) || s.image_url.split('/').includes('..'))) throw new Error('Saved images must use this site’s image URLs.')
    image = s.image_url
  }
  return { date: s.date as string, group_id: s.group_id as string, headline: s.headline as string,
    category: s.category as string, saved_at: s.saved_at as number, ...(image === undefined ? {} : { image_url: image }) }
}

/** Validate the entire backup before merging; a rejected import never changes the current library. */
export function importLibrary(raw: string, current: Library): Library {
  if (new TextEncoder().encode(raw).length > MAX_IMPORT_BYTES) throw new Error('Choose a library backup smaller than 2 MB.')
  let data: unknown
  try { data = JSON.parse(raw) } catch { throw new Error('This file is not valid JSON.') }
  if (!data || typeof data !== 'object') throw new Error('This is not a NewsSense library backup.')
  const backup = data as Record<string, unknown>
  if (backup.version !== 1 || !Array.isArray(backup.saved) || backup.saved.length > 300) {
    throw new Error('Use a version 1 NewsSense library backup with at most 300 saved stories.')
  }
  const saved = backup.saved.map(article)
  const categories = topics(backup.categories)
  const keywords = topics(backup.keywords)
  if (backup.stories !== undefined && (!Array.isArray(backup.stories) || backup.stories.length > MAX_FOLLOWED_STORIES)) {
    throw new Error(`A backup can contain up to ${MAX_FOLLOWED_STORIES} followed stories.`)
  }
  const stories: FollowedStory[] = (backup.stories as Record<string, unknown>[] | undefined ?? []).map((s) => {
    if (!s || typeof s !== 'object' || (s.content_version !== undefined && (typeof s.content_version !== 'string' || !/^[a-f0-9]{64}$/.test(s.content_version)))
      || (s.story_identity !== undefined && (typeof s.story_identity !== 'string' || !s.story_identity || s.story_identity.length > 200))) {
      throw new Error('A followed story has an invalid content version.')
    }
    const checked = article({ ...s, saved_at: s.followed_at })
    return { date: checked.date, group_id: checked.group_id, headline: checked.headline, category: checked.category,
      followed_at: checked.saved_at, ...(s.content_version === undefined ? {} : { content_version: s.content_version as string }),
      ...(s.story_identity === undefined ? {} : { story_identity: s.story_identity as string }) }
  })
  const merged = new Map<string, SavedArticle>()
  for (const s of [...saved, ...current.saved]) {
    const key = `${s.date}/${s.group_id}`
    if (!merged.has(key) || merged.get(key)!.saved_at <= s.saved_at) merged.set(key, s)
  }
  const followed = new Map<string, FollowedStory>()
  for (const s of [...stories, ...current.stories]) {
    const key = `${s.date}/${s.group_id}`
    if (!followed.has(key) || followed.get(key)!.followed_at <= s.followed_at) followed.set(key, s)
  }
  if (followed.size > MAX_FOLLOWED_STORIES) throw new Error(`Import would exceed ${MAX_FOLLOWED_STORIES} followed stories. Remove some from Saved first.`)
  return {
    saved: [...merged.values()].sort((a, b) => b.saved_at - a.saved_at).slice(0, 300),
    categories: [...new Set([...current.categories, ...categories])],
    keywords: [...new Set([...current.keywords, ...keywords])],
    stories: [...followed.values()].sort((a, b) => b.followed_at - a.followed_at),
  }
}
