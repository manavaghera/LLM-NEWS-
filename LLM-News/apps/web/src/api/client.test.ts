import { afterEach, expect, it, vi } from 'vitest'
import { api } from './client'

afterEach(() => vi.unstubAllGlobals())

it('preserves admin authentication headers while supplying JSON defaults', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}', { headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  await api.operations('test-only-token')
  const headers = fetch.mock.calls[0][1].headers as Headers
  expect(headers.get('X-Admin-Token')).toBe('test-only-token')
  expect(headers.get('Accept')).toBe('application/json')
})

it('sends a budget mutation with authentication and a JSON body', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}'))
  vi.stubGlobal('fetch', fetch)
  await api.budget('test-only-token', 12)
  const [url, options] = fetch.mock.calls[0]
  expect(url).toBe('/api/operations/budget')
  expect(options.method).toBe('PATCH')
  expect(options.headers.get('X-Admin-Token')).toBe('test-only-token')
  expect(options.headers.get('Content-Type')).toBe('application/json')
  expect(JSON.parse(options.body)).toEqual({ daily_call_limit: 12 })
})
