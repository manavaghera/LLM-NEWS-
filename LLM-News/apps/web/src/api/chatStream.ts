import { splitSSE } from '@/lib/sse'
import { readError } from './client'
import type { ChatEvent, ChatTurn } from './types'

export interface ChatStreamRequest {
  message: string
  model?: string
  history: ChatTurn[]
  context?: { currentGroupId?: string; currentDate: string }
}

/** POST /api/chat/stream and call onEvent for each server-sent event until the reply is done. */
export async function streamChat(
  body: ChatStreamRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) throw await readError(response)

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const { payloads, rest } = splitSSE(buffer + value)
    buffer = rest
    for (const payload of payloads) {
      try {
        onEvent(JSON.parse(payload) as ChatEvent)
      } catch {
        // ignore malformed events
      }
    }
  }
}
