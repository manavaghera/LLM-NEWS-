import { describe, expect, it } from 'vitest'
import type { ModelSnapshot } from '@/api/types'
import { monthlyModelCost, parseModelPreferences, selfHostEstimate } from './modelTools'

const model = { input_price: 2, output_price: 10 } as ModelSnapshot

describe('model tools', () => {
  it('calculates a monthly workload from per-million token prices', () => {
    expect(monthlyModelCost(model, 100, 1000, 200, 30)).toBeCloseTo(12)
  })

  it('estimates whole GPUs and hardware cost', () => {
    expect(selfHostEstimate(70, 24, 900)).toEqual({ gpuCount: 3, hardwareCost: 2700 })
  })

  it('rejects malformed stored preferences and limits comparisons', () => {
    expect(parseModelPreferences('bad').selected).toEqual([])
    expect(parseModelPreferences(JSON.stringify({ selected: ['a', 'b', 'c', 'd', 'e'], priceTargets: { a: 2, bad: 'x' } }))).toMatchObject({
      selected: ['a', 'b', 'c', 'd'], priceTargets: { a: 2 },
    })
  })
})
