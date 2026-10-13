import type { ModelSnapshot } from '@/api/types'

export interface ModelPreferences {
  selected: string[]
  watched: string[]
  priceTargets: Record<string, number>
  benchmarkScores: Record<string, number>
  digestTopics: string[]
}

export const EMPTY_MODEL_PREFERENCES: ModelPreferences = {
  selected: [], watched: [], priceTargets: {}, benchmarkScores: {}, digestTopics: [],
}

const strings = (value: unknown) => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string').slice(0, 50)
  : []

const numbers = (value: unknown) => value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).filter(([, item]) => typeof item === 'number' && Number.isFinite(item)))
  : {}

export function parseModelPreferences(raw: string | null): ModelPreferences {
  if (!raw) return EMPTY_MODEL_PREFERENCES
  try {
    const value = JSON.parse(raw)
    if (!value || typeof value !== 'object') return EMPTY_MODEL_PREFERENCES
    return {
      selected: strings(value.selected).slice(0, 4),
      watched: strings(value.watched),
      priceTargets: numbers(value.priceTargets),
      benchmarkScores: numbers(value.benchmarkScores),
      digestTopics: strings(value.digestTopics),
    }
  } catch {
    return EMPTY_MODEL_PREFERENCES
  }
}

export function monthlyModelCost(model: ModelSnapshot, requestsPerDay: number, inputTokens: number, outputTokens: number, days: number): number {
  const requests = Math.max(0, requestsPerDay) * Math.max(0, days)
  return requests * ((Math.max(0, inputTokens) / 1_000_000) * model.input_price
    + (Math.max(0, outputTokens) / 1_000_000) * model.output_price)
}

export function selfHostEstimate(requiredMemoryGb: number, gpuMemoryGb: number, gpuPrice: number) {
  const count = gpuMemoryGb > 0 ? Math.ceil(Math.max(0, requiredMemoryGb) / gpuMemoryGb) : 0
  return { gpuCount: count, hardwareCost: count * Math.max(0, gpuPrice) }
}

export function modelsCsv(models: ModelSnapshot[]): string {
  const cell = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const rows = [['Model', 'Provider', 'Input USD/MTok', 'Output USD/MTok', 'Context', 'Max output', 'Open weights'],
    ...models.map((model) => [model.name, model.provider, model.input_price, model.output_price,
      model.context_tokens, model.max_output_tokens ?? '', model.open_weights ? 'Yes' : 'No'])]
  return rows.map((row) => row.map(cell).join(',')).join('\n')
}
