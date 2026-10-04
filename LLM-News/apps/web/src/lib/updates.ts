import type { NewsItem, UpdateStatus } from '@/api/types'

const MINUTE = 60_000
const NEW_FOR = 3 * 60 * MINUTE

const timeOf = (iso?: string | null) => (iso ? Date.parse(iso) : NaN)
const addedAt = (item: NewsItem) => timeOf(item.added_at) || 0

/** "in 34 min", "in 1 h 5 min", or "any moment now" once it is due */
export function countdown(nextUpdate: string, now: number): string {
  const minutes = Math.ceil((timeOf(nextUpdate) - now) / MINUTE)
  if (!(minutes > 0)) return 'any moment now'
  if (minutes < 60) return `in ${minutes} min`
  const hours = Math.floor(minutes / 60)
  return minutes % 60 ? `in ${hours} h ${minutes % 60} min` : `in ${hours} h`
}

/** The updater is still running: its next update is due, or overdue by less than one interval
 * (an update takes a few minutes). Otherwise there is nothing to count down to. */
export function updatesRunning(status: UpdateStatus | undefined, now: number): boolean {
  const next = timeOf(status?.next_update)
  return Number.isFinite(next) && now < next + Math.max(status?.interval_minutes ?? 60, 30) * MINUTE
}

/** Stories an hourly update added after the edition's first batch, in the last 3 hours. Stories without a
 * time were written before updates recorded one, so they belong to the first batch. */
export function newStories(items: NewsItem[], now: number): Set<string> {
  const times = items.map(addedAt)
  if (!times.some((t) => t > 0)) return new Set()
  const first = Math.min(...times)
  return new Set(items.filter((i) => addedAt(i) > first && now - addedAt(i) < NEW_FOR).map((i) => i.group_id))
}

/** Latest update first; within one update (and for stories without a time) the writer's order */
export function byUpdate(items: NewsItem[]): NewsItem[] {
  return [...items].sort((a, b) => addedAt(b) - addedAt(a))
}

/** The front page's lead: the story most outlets covered, a pictured one if possible, the newest on a tie */
export function pickLead(items: NewsItem[]): NewsItem {
  const pictured = items.filter((item) => item.has_image !== false)
  const pool = pictured.length ? pictured : items
  const sources = (item: NewsItem) => item.source_count ?? 0
  return pool.reduce((best, item) =>
    sources(item) > sources(best) || (sources(item) === sources(best) && addedAt(item) > addedAt(best)) ? item : best,
  )
}
