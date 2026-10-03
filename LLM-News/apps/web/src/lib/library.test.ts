import { describe, expect, it } from 'vitest'
import type { NewsItem } from '@/api/types'
import { matchesFollows, parseLibrary, toggleIn, toggleSaved } from './library'
import { parseInline } from './markdown'

const item = (over: Partial<NewsItem> = {}): NewsItem => ({
  id: 1, group_id: 'group_1', headline: 'UN extends Haiti force', category: 'social', content: '',
  summary: 'The Security Council voted.', date: '2026-10-02', image_url: '', ...over,
})

describe('library', () => {
  it('ignores corrupt or tampered storage', () => {
    expect(parseLibrary('not json')).toEqual({ saved: [], categories: [], keywords: [] })
    expect(parseLibrary('{"saved":[{"date":1}],"categories":["tech",5],"keywords":"x"}')).toEqual({
      saved: [], categories: ['tech'], keywords: [],
    })
  })

  it('saves and unsaves an article, newest first', () => {
    const empty = parseLibrary(null)
    const a = { date: '2026-10-01', group_id: 'group_1', headline: 'A', category: 'tech' }
    const b = { date: '2026-10-02', group_id: 'group_1', headline: 'B', category: 'social' }
    const both = toggleSaved(toggleSaved(empty, a, 1), b, 2)
    expect(both.saved.map((s) => s.headline)).toEqual(['B', 'A'])
    expect(toggleSaved(both, a).saved.map((s) => s.headline)).toEqual(['B'])
  })

  it('follows categories and keywords case-insensitively', () => {
    expect(toggleIn(['tech'], ' Haiti ')).toEqual(['tech', 'haiti'])
    expect(toggleIn(['tech', 'haiti'], 'HAITI')).toEqual(['tech'])
    const lib = { saved: [], categories: ['tech'], keywords: ['security council'] }
    expect(matchesFollows(item(), lib)).toBe(true) // keyword in summary
    expect(matchesFollows(item({ summary: 'Nothing', category: 'tech' }), lib)).toBe(true)
    expect(matchesFollows(item({ summary: 'Nothing' }), lib)).toBe(false)
  })
})

describe('chat citations', () => {
  it('turns [n] into citation parts', () => {
    expect(parseInline('Rates held [1][2].').map((p) => p.kind)).toEqual(['text', 'cite', 'cite', 'text'])
    expect(parseInline('Array[1234] stays text').every((p) => p.kind === 'text')).toBe(true)
  })
})
