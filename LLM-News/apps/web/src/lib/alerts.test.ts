import { describe, expect, it } from 'vitest'
import type { NewsItem } from '@/api/types'
import { discoverAlerts, discoverStoryAlerts, parseAlerts } from './alerts'

const story: NewsItem = { id: 1, date: '2026-01-02', group_id: 'group_1', headline: 'Processor launched', category: 'tech', content: '', summary: 'Faster chips', image_url: '' }
const follows = { saved: [], categories: ['tech'], keywords: [] }

describe('local story alerts', () => {
  it('adds matching stories once and keeps read alerts read after reload', () => {
    const first = discoverAlerts({ items: [], seen: [] }, [story, { ...story, group_id: 'group_2', category: 'social' }], follows)
    expect(first.items).toHaveLength(1)
    const read = parseAlerts(JSON.stringify({ ...first, items: [{ ...first.items[0], read: true }] }))
    expect(discoverAlerts(read, [story], follows)).toBe(read)
    expect(read.items[0].read).toBe(true)
  })

  it('distinguishes editions and supports followed search keywords', () => {
    const first = discoverAlerts({ items: [], seen: [] }, [story], follows)
    const next = discoverAlerts(first, [{ ...story, date: '2026-01-03', category: 'social' }], { ...follows, categories: [], keywords: ['chips'] })
    expect(next.items.map((s) => s.date)).toEqual(['2026-01-03', '2026-01-02'])
  })

  it('does not alert before the reader follows anything and rejects corrupt storage', () => {
    expect(discoverAlerts({ items: [], seen: [] }, [story], { categories: [], keywords: [] }).items).toEqual([])
    expect(parseAlerts('invalid')).toEqual({ items: [], seen: [] })
    expect(parseAlerts('{"items":[{"key":1}],"seen":[]}').items).toEqual([])
  })

  it('alerts on later coverage and changed content once, retaining version checkpoints across reloads', () => {
    const followed = { ...story, followed_at: 10, story_identity: 'original', content_version: 'first' }
    const baseline = { date: story.date, group_id: story.group_id, story_identity: 'original', content_version: 'first', updates: [] }
    const initial = discoverStoryAlerts({ items: [], seen: [] }, followed, baseline)
    expect(initial.items).toEqual([])
    const response = { ...baseline, content_version: 'second', updates: [{ ...story, date: '2026-01-03', story_identity: 'later', content_version: 'later-v1', shared_topics: ['chips'] }] }
    const changed = discoverStoryAlerts(initial, followed, response)
    expect(changed.items.map((item) => item.kind)).toEqual(['updated', 'coverage'])
    const loaded = parseAlerts(JSON.stringify({ ...changed, items: changed.items.map((item) => ({ ...item, read: true })) }))
    expect(discoverStoryAlerts(loaded, followed, response)).toBe(loaded)
    expect(discoverStoryAlerts(loaded, { ...followed, group_id: 'group_2' }, { ...response, group_id: 'group_2', content_version: 'first' }).items).toHaveLength(2)
  })

  it('ignores a replacement story when its dated group ID is reused', () => {
    const followed = { ...story, followed_at: 10, story_identity: 'original', content_version: 'first' }
    const result = discoverStoryAlerts({ items: [], seen: [] }, followed, { date: story.date, group_id: story.group_id,
      story_identity: 'replacement', content_version: 'different', updates: [{ ...story, content_version: 'new', shared_topics: [] }] })
    expect(result.items).toEqual([])
    expect(result.unavailable).toEqual([`${story.date}/${story.group_id}`])
  })

  it('deduplicates a later article already announced by a category alert', () => {
    const later = { ...story, date: '2026-01-03', story_identity: 'later', content_version: 'later-v1', shared_topics: [] }
    const topics = discoverAlerts({ items: [], seen: [] }, [later], follows)
    const followed = { ...story, followed_at: 10, story_identity: 'original', content_version: 'first' }
    const result = discoverStoryAlerts(topics, followed, { date: story.date, group_id: story.group_id,
      story_identity: 'original', content_version: 'first', updates: [later] })
    expect(result.items).toHaveLength(1)
    expect(result.items[0].headline).toBe(later.headline)
  })
})
