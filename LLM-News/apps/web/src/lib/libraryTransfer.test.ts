import { describe, expect, it } from 'vitest'
import type { Library } from './library'
import { exportLibrary, importLibrary } from './libraryTransfer'

const saved = { date: '2026-01-02', group_id: 'group_1', headline: 'Story', category: 'tech', saved_at: 10, image_url: '/static/images/2026-01-02/group_1.jpg' }
const current: Library = { saved: [saved], categories: ['tech'], keywords: ['chips'], stories: [] }

describe('library backups', () => {
  it('round trips saved stories and followed topics without duplicates', () => {
    const backup = exportLibrary({ saved: [{ ...saved, saved_at: 5 }, { ...saved, group_id: 'group_2', saved_at: 20 }], categories: ['Tech', 'social'], keywords: [' Chips ', 'Haiti'], stories: [] })
    const merged = importLibrary(backup, current)
    expect(merged.saved.map((s) => [s.group_id, s.saved_at])).toEqual([['group_2', 20], ['group_1', 10]])
    expect(merged.categories).toEqual(['tech', 'social'])
    expect(merged.keywords).toEqual(['chips', 'haiti'])
    expect(importLibrary(backup, merged)).toEqual(merged)
  })

  it.each([
    { ...saved, date: '2026-02-30' },
    { ...saved, group_id: '../private' },
    { ...saved, saved_at: 'yesterday' },
    { ...saved, image_url: 'https://tracker.example/pixel' },
    { ...saved, image_url: '/static/images/../../../api/private' },
    { ...saved, headline: null },
  ])('rejects an invalid story without changing the current library', (bad) => {
    const before = exportLibrary(current)
    expect(() => importLibrary(JSON.stringify({ version: 1, saved: [bad], categories: [], keywords: [] }), current)).toThrow()
    expect(exportLibrary(current)).toBe(before)
  })

  it('rejects unsupported versions and malformed topic lists', () => {
    expect(() => importLibrary('{', current)).toThrow('JSON')
    expect(() => importLibrary(JSON.stringify({ version: 2, saved: [], categories: [], keywords: [] }), current)).toThrow('version 1')
    expect(() => importLibrary(JSON.stringify({ version: 1, saved: [], categories: [3], keywords: [] }), current)).toThrow('Topics')
  })

  it('exports story follows with their identities and baselines, merging repeated imports', () => {
    const story = { date: saved.date, group_id: saved.group_id, headline: saved.headline, category: saved.category,
      followed_at: 10, story_identity: 'a'.repeat(64), content_version: 'b'.repeat(64) }
    const backup = exportLibrary({ ...current, stories: [story] })
    const imported = importLibrary(backup, current)
    expect(imported.stories).toEqual([story])
    expect(importLibrary(backup, imported).stories).toEqual([story])
    expect(() => importLibrary(JSON.stringify({ ...JSON.parse(backup), stories: [{ ...story, content_version: 'invalid' }] }), current)).toThrow('version')
  })
})
