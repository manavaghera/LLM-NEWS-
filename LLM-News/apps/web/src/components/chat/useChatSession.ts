import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { streamChat } from '@/api/chatStream'
import type { ChatEvent, ChatSource, ChatTurn } from '@/api/types'
import { storage } from '@/lib/utils'
import type { ChatScope } from './ChatProvider'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'streaming' | 'done' | 'error' | 'stopped'
  model?: string
  sources?: ChatSource[]
}

const PREFIX = 'newssense-chat:'
const MAX_SAVED = 40
const MAX_HISTORY = 12 // the backend accepts up to 12 earlier turns

export const sessionKey = (scope: ChatScope) => (scope ? `${scope.date}/${scope.groupId}` : 'general')

function load(key: string): ChatMessage[] {
  try {
    const saved = JSON.parse(storage.get(PREFIX + key) ?? '[]')
    return Array.isArray(saved) ? saved.filter((m) => m && typeof m.content === 'string') : []
  } catch {
    return []
  }
}

const newId = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()))

/** One conversation per article (or the general one), kept only in this browser. */
export function useChatSession(scope: ChatScope, editionDate?: string) {
  const key = sessionKey(scope)
  const [sessions, setSessions] = useState<Record<string, ChatMessage[]>>({})
  const saved = useMemo(() => load(key), [key])
  const messages = sessions[key] ?? saved
  const controllers = useRef(new Map<string, AbortController>())
  const busy = messages.some((m) => m.status === 'streaming')

  const update = useCallback(
    (fn: (messages: ChatMessage[]) => ChatMessage[]) =>
      setSessions((prev) => ({ ...prev, [key]: fn(prev[key] ?? load(key)) })),
    [key],
  )

  useEffect(() => {
    const finished = messages.filter((m) => m.status !== 'streaming').slice(-MAX_SAVED)
    if (finished.length) storage.set(PREFIX + key, JSON.stringify(finished))
  }, [key, messages])

  useEffect(() => {
    const active = controllers.current
    return () => {
      active.forEach((controller) => controller.abort())
      active.clear()
    }
  }, [])

  const send = async (text: string, model?: string) => {
    const message = text.trim()
    if (!message || busy || controllers.current.has(key)) return
    const controller = new AbortController()
    controllers.current.set(key, controller)
    const replyId = newId()
    const patchReply = (patch: (m: ChatMessage) => Partial<ChatMessage>) =>
      update((list) => list.map((m) => (m.id === replyId ? { ...m, ...patch(m) } : m)))
    const history: ChatTurn[] = messages
      .filter((m) => m.status === 'done' && m.content)
      .slice(-MAX_HISTORY)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }))

    update((list) => [
      ...list,
      { id: newId(), role: 'user', content: message, status: 'done' },
      { id: replyId, role: 'assistant', content: '', status: 'streaming' },
    ])

    const onEvent = (event: ChatEvent) => {
      if (event.type === 'meta') patchReply(() => ({ model: event.model, sources: event.sources ?? [] }))
      else if (event.type === 'delta') patchReply((m) => ({ content: m.content + event.text }))
      else if (event.type === 'error') patchReply(() => ({ content: event.message, status: 'error' }))
      else if (event.type === 'done') patchReply((m) => (m.status === 'streaming' ? { status: 'done' } : {}))
    }
    try {
      await streamChat(
        {
          message,
          model,
          history,
          context: scope
            ? { currentGroupId: scope.groupId, currentDate: scope.date }
            : editionDate ? { currentDate: editionDate } : undefined,
        },
        onEvent,
        controller.signal,
      )
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        patchReply(() => ({ status: 'stopped' }))
      } else {
        patchReply(() => ({ content: error instanceof Error ? error.message : 'Something went wrong.', status: 'error' }))
      }
    } finally {
      if (controllers.current.get(key) === controller) controllers.current.delete(key)
      patchReply((m) => (m.status === 'streaming' ? { status: 'done' } : {}))
    }
  }

  const stop = () => controllers.current.get(key)?.abort()

  const clear = () => {
    stop()
    controllers.current.delete(key)
    storage.remove(PREFIX + key)
    setSessions((prev) => ({ ...prev, [key]: [] }))
  }

  return { messages, busy, send, stop, clear }
}
