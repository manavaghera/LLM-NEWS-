import { describe, expect, it } from 'vitest'
import type { NewsItem } from '@/api/types'
import { matchesFollows, MAX_FOLLOWED_STORIES, parseLibrary, toggleFollowedStory, toggleIn, toggleSaved } from './library'
import { parseInline } from './markdown'

const item = (over: Partial<NewsItem> = {}): NewsItem => ({
  id: 1, group_id: 'group_1', headline: 'UN extends Haiti force', category: 'social', content: '',
  summary: 'The Security Council voted.', date: '2026-10-02', image_url: '', ...over,
})

describe('library', () => {
  it('ignores corrupt or tampered storage', () => {
    expect(parseLibrary('not json')).toEqual({ saved: [], categories: [], keywords: [], stories: [] })
    expect(parseLibrary('{"saved":[{"date":1}],"categories":["tech",5],"keywords":"x"}')).toEqual({
      saved: [], categories: ['tech'], keywords: [], stories: [],
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

  it('bounds explicit story follows, supports removing one and replaces reused locations only on request', () => {
    const story = { date: '2026-01-02', group_id: 'group_1', headline: 'Original story', category: 'tech', story_identity: 'original' }
    let lib = parseLibrary(null)
    for (let i = 0; i < MAX_FOLLOWED_STORIES; i++) lib = toggleFollowedStory(lib, { ...story, group_id: `group_${i + 1}` }, i)
    expect(() => toggleFollowedStory(lib, { ...story, group_id: 'group_999' })).toThrow('20 stories')
    const replaced = toggleFollowedStory(lib, { ...story, headline: 'Replacement story', story_identity: 'replacement' }, 50)
    expect(replaced.stories).toHaveLength(MAX_FOLLOWED_STORIES)
    expect(replaced.stories[0].headline).toBe('Replacement story')
    expect(toggleFollowedStory(replaced, replaced.stories[0]).stories).toHaveLength(MAX_FOLLOWED_STORIES - 1)
  })
})

describe('chat citations', () => {
  it('turns [n] into citation parts', () => {
    expect(parseInline('Rates held [1][2].').map((p) => p.kind)).toEqual(['text', 'cite', 'cite', 'text'])
    expect(parseInline('Array[1234] stays text').every((p) => p.kind === 'text')).toBe(true)
  })
})
