import * as Dialog from '@radix-ui/react-dialog'
import { ArrowUp, Bot, MessageCircle, Square, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useModels } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { useEdition } from '@/hooks/useEdition'
import { cn, storage } from '@/lib/utils'
import { useChat } from './ChatProvider'
import { Markdown } from './Markdown'
import { useChatSession, type ChatMessage } from './useChatSession'

const MODEL_KEY = 'newssense-model'
const ARTICLE_PROMPTS = ['Summarise this in 3 bullet points', 'Who is involved and what happened?', 'Why does this story matter?']
const GENERAL_PROMPTS = ["What are today's biggest stories?", "What's new in technology today?", 'Give me a quick world news briefing']

export function ChatLauncher() {
  const { open, setOpen, pageScope } = useChat()
  if (open) return null
  return (
    <Button
      variant="primary"
      onClick={() => setOpen(true)}
      className="fixed right-4 bottom-4 z-30 h-12 px-5 shadow-lg sm:right-6 sm:bottom-6"
    >
      <MessageCircle /> {pageScope ? 'Ask about this story' : 'Ask AI'}
    </Button>
  )
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-sm text-paper">{message.content}</div>
  }
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent" aria-hidden>
        <Bot className="size-4" />
      </span>
      <div className="min-w-0 flex-1 text-sm leading-relaxed">
        {message.status === 'error' ? (
          <p className="rounded-xl bg-negative/10 px-3 py-2 text-negative">{message.content}</p>
        ) : message.content ? (
          <Markdown source={message.content} sources={message.sources} />
        ) : (
          <p className="text-faint">Thinking…</p>
        )}
        {message.status === 'streaming' && message.content && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-text-bottom" aria-hidden />}
        {message.status === 'stopped' && <p className="mt-1 text-xs text-faint">Stopped</p>}
      </div>
    </div>
  )
}

export function ChatPanel() {
  const { open, setOpen, scope, setScope, pageScope } = useChat()
  const { date } = useEdition()
  const { messages, busy, send, stop, clear } = useChatSession(scope, date)
  const models = useModels()
  const [draft, setDraft] = useState('')
  const [model, setModel] = useState(() => storage.get(MODEL_KEY) ?? '')
  const end = useRef<HTMLDivElement>(null)

  const choices = (models.data?.models ?? []).filter((m) => m.value !== 'knowledge-graph')
  const selected = choices.some((m) => m.value === model) ? model : models.data?.default?.value

  const last = messages.at(-1)
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, last?.content, open])

  const submit = (text = draft) => {
    if (!text.trim() || busy) return
    setDraft('')
    void send(text, selected)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen} modal={false}>
      <Dialog.Portal>
        <Dialog.Content
          onInteractOutside={(event) => event.preventDefault()}
          className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-rule bg-surface shadow-2xl sm:w-[420px]"
        >
          <header className="space-y-3 border-b border-rule p-4">
            <div className="flex items-center gap-2">
              <Dialog.Title className="font-semibold">Ask NewsSense</Dialog.Title>
              <div className="ml-auto flex items-center gap-1">
                {messages.length > 0 && (
                  <Button variant="ghost" size="icon" onClick={clear} aria-label="Clear conversation">
                    <Trash2 />
                  </Button>
                )}
                <Dialog.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Close chat">
                    <X />
                  </Button>
                </Dialog.Close>
              </div>
            </div>
            <Dialog.Description className="text-xs text-muted">
              {scope ? (
                <span className="flex items-center gap-2">
                  <span className="line-clamp-1">About: <strong className="font-medium text-ink">{scope.headline}</strong></span>
                  <button type="button" onClick={() => setScope(null)} className="shrink-0 underline hover:text-ink">Ask generally</button>
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Answers come from this edition&apos;s stories.
                  {pageScope && (
                    <button type="button" onClick={() => setScope(pageScope)} className="underline hover:text-ink">Ask about this story</button>
                  )}
                </span>
              )}
            </Dialog.Description>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto p-4" aria-live="polite">
            {messages.length === 0 && (
              <div className="space-y-3 pt-6">
                <p className="text-sm text-muted">Try asking:</p>
                {(scope ? ARTICLE_PROMPTS : GENERAL_PROMPTS).map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => submit(prompt)}
                    className="block w-full rounded-xl border border-rule px-4 py-3 text-left text-sm hover:bg-sunken"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}
            {messages.map((message) => <Message key={message.id} message={message} />)}
            <div ref={end} />
          </div>

          <footer className="space-y-2 border-t border-rule p-3">
            <div className="flex items-end gap-2 rounded-2xl border border-rule bg-paper p-2 focus-within:border-faint">
              <label htmlFor="chat-input" className="sr-only">Your question</label>
              <textarea
                id="chat-input"
                rows={1}
                maxLength={2000}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={scope ? 'Ask about this story…' : 'Ask about the news…'}
                className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none field-sizing-content placeholder:text-faint"
              />
              {busy ? (
                <Button variant="outline" size="icon" onClick={stop} aria-label="Stop answering">
                  <Square />
                </Button>
              ) : (
                <Button variant="primary" size="icon" onClick={() => submit()} disabled={!draft.trim()} aria-label="Send">
                  <ArrowUp />
                </Button>
              )}
            </div>
            <div className="flex items-center justify-between gap-2 px-1 text-xs text-faint">
              <span>AI can make mistakes. Check the sources.</span>
              {choices.length > 1 ? (
                <label className="flex items-center gap-1">
                  <span className="sr-only">Model</span>
                  <select
                    value={selected}
                    onChange={(e) => {
                      setModel(e.target.value)
                      storage.set(MODEL_KEY, e.target.value)
                    }}
                    className="bg-transparent text-xs text-muted"
                  >
                    {choices.map((m) => <option key={m.value} value={m.value}>{m.name}</option>)}
                  </select>
                </label>
              ) : (
                selected && <span className={cn('truncate')}>{choices[0]?.name ?? selected}</span>
              )}
            </div>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
