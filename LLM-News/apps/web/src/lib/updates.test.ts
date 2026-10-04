import { describe, expect, it } from 'vitest'
import type { NewsItem } from '@/api/types'
import { byUpdate, countdown, newStories, pickLead, updatesRunning } from './updates'

const at = (time: string) => `2026-10-04T${time}:00+05:30`
const now = Date.parse(at('14:30'))

function story(group_id: string, added?: string, source_count = 1, has_image = true): NewsItem {
  return {
    id: 0, group_id, headline: group_id, category: 'social', content: '', summary: '', date: '2026-10-04',
    image_url: '', has_image, source_count, added_at: added ? at(added) : null,
  }
}

describe('update countdown', () => {
  it('counts down in minutes and hours', () => {
    expect(countdown(at('15:04'), now)).toBe('in 34 min')
    expect(countdown(at('15:30'), now)).toBe('in 1 h')
    expect(countdown(at('15:35'), now)).toBe('in 1 h 5 min')
    expect(countdown(at('14:30'), now)).toBe('any moment now')
  })

  it('only counts down while the updater runs', () => {
    const status = { date: '2026-10-04', last_update: at('13:30'), interval_minutes: 60, added: 0 }
    expect(updatesRunning({ ...status, next_update: at('14:20') }, now)).toBe(true) // a few minutes overdue
    expect(updatesRunning({ ...status, next_update: at('13:20') }, now)).toBe(false) // stopped
    expect(updatesRunning(undefined, now)).toBe(false)
  })
})

describe('hourly stories', () => {
  const morning = [story('group_1', '07:00', 3), story('group_2', '07:00')]
  const items = [...morning, story('group_3', '13:00', 4), story('group_4', '09:00')]

  it('marks stories added after the first batch, for 3 hours', () => {
    expect(newStories(items, now)).toEqual(new Set(['group_3']))
    expect(newStories(morning, now).size).toBe(0)
    expect(newStories([story('group_1')], now).size).toBe(0) // older editions have no times
    expect(newStories([story('group_1'), story('group_2', '13:00')], now)).toEqual(new Set(['group_2'])) // untimed = first batch
  })

  it('puts the latest update first and keeps the order within one', () => {
    expect(byUpdate(items).map((i) => i.group_id)).toEqual(['group_3', 'group_4', 'group_1', 'group_2'])
  })

  it('leads with the most-covered story, preferring pictures and then the newest', () => {
    expect(pickLead(items).group_id).toBe('group_3')
    expect(pickLead([story('group_1', '07:00', 2), story('group_2', '08:00', 2)]).group_id).toBe('group_2')
    expect(pickLead([story('group_1', '07:00', 5, false), story('group_2', '07:00', 1)]).group_id).toBe('group_2')
  })
})
