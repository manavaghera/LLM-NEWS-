import type { ArticleSection } from '@/api/types'

export const CATEGORIES = [
  { value: 'social', label: 'Social', section: 'World & Society', tone: 'text-social', bg: 'bg-social' },
  { value: 'tech', label: 'Technology', section: 'Technology', tone: 'text-tech', bg: 'bg-tech' },
  { value: 'entertainment', label: 'Entertainment', section: 'Culture & Entertainment', tone: 'text-entertainment', bg: 'bg-entertainment' },
] as const

export type CategoryInfo = { value: string; label: string; section: string; tone: string; bg: string }

export function categoryInfo(value: string | undefined): CategoryInfo {
  const known = CATEGORIES.find((c) => c.value === value?.toLowerCase())
  if (known) return known
  const label = value ? value.charAt(0).toUpperCase() + value.slice(1) : 'General'
  return { value: value ?? 'general', label, section: label, tone: 'text-muted', bg: 'bg-muted' }
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

/** "2026-09-30" -> Date at local noon (avoids timezone day shifts). */
function parseDay(date: string): Date | null {
  if (!DATE_ONLY.test(date)) return null
  const [y, m, d] = date.split('-').map(Number)
  return new Date(y, m - 1, d, 12)
}

export function formatLongDate(date: string): string {
  const day = parseDay(date)
  return day
    ? day.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    : date
}

export function formatShortDate(date: string): string {
  const day = parseDay(date)
  return day ? day.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : date
}

export function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

export type Tone = 'positive' | 'negative' | 'neutral'

export function sentimentOf(section: ArticleSection): { value: number; label: string; tone: Tone } | null {
  const value = toNumber(section.sentisement_from_the_content)
  if (value === null) return null
  if (value >= 0.15) return { value, label: 'Positive', tone: 'positive' }
  if (value <= -0.15) return { value, label: 'Negative', tone: 'negative' }
  return { value, label: 'Neutral', tone: 'neutral' }
}

/** Reliability from the fake-news classifier, else the publishers' trust score; null when the section
 *  was not scored (never guessed). */
export function reliabilityOf(
  section: ArticleSection,
): { label: string; score: number; basis: 'classifier' | 'publisher' } | null {
  const fake = toNumber(section.fake_news_probability)
  const score = fake !== null ? 1 - fake : toNumber(section.publisher_reliability_score)
  if (score === null) return null
  return {
    score,
    label: score >= 0.6 ? 'High' : score >= 0.3 ? 'Medium' : 'Low',
    basis: fake !== null ? 'classifier' : 'publisher',
  }
}

const REGIONS: Record<string, string> = {
  us: 'United States', uk: 'United Kingdom', gb: 'United Kingdom', ca: 'Canada', qa: 'Qatar',
  au: 'Australia', my: 'Malaysia', tw: 'Taiwan', in: 'India', de: 'Germany', fr: 'France',
}

export const regionName = (code: string) => REGIONS[code.toLowerCase()] ?? code.toUpperCase()

/** "BBCNews" -> "BBC News", "TheGuardian" -> "The Guardian" */
export function publisherName(name: string): string {
  return name.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
}

export function plural(count: number, word: string): string {
  if (count === 1) return `${count} ${word}`
  return `${count} ${/[^aeiou]y$/.test(word) ? `${word.slice(0, -1)}ies` : `${word}s`}`
}
