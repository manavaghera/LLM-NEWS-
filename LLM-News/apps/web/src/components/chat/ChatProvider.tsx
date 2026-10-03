import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

/** The article the assistant is answering about; null means general news questions. */
export type ChatScope = { date: string; groupId: string; headline: string } | null

interface ChatState {
  open: boolean
  setOpen: (open: boolean) => void
  scope: ChatScope
  setScope: (scope: ChatScope) => void
  /** Article on screen, which the reader can switch back to after asking general questions. */
  pageScope: ChatScope
  setPageScope: (scope: ChatScope) => void
}

const ChatContext = createContext<ChatState | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [scope, setScope] = useState<ChatScope>(null)
  const [pageScope, setPageScope] = useState<ChatScope>(null)
  const value = useMemo(
    () => ({ open, setOpen, scope, setScope, pageScope, setPageScope }),
    [open, scope, pageScope],
  )
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatState {
  const state = useContext(ChatContext)
  if (!state) throw new Error('useChat must be used inside <ChatProvider>')
  return state
}

/** Scope the assistant to the article on screen while this page is mounted. */
export function useArticleChatScope(date?: string, groupId?: string, headline?: string) {
  const { setScope, setPageScope } = useChat()
  useEffect(() => {
    if (!date || !groupId || !headline) return
    const scope = { date, groupId, headline }
    setScope(scope)
    setPageScope(scope)
    return () => {
      setScope(null)
      setPageScope(null)
    }
  }, [date, groupId, headline, setScope, setPageScope])
}
