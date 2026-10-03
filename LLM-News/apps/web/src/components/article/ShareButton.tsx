import { Check, Share2 } from 'lucide-react'
import { useState } from 'react'
import { media } from '@/api/client'
import { Button } from '@/components/ui/button'

/** Shares the /share/... link, whose preview tags give chat apps and social sites a proper card */
export function ShareButton({ date, groupId, title }: { date: string; groupId: string; title: string }) {
  const [copied, setCopied] = useState(false)
  const url = media.share(date, groupId)

  const share = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url })
        return
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return // closed the share sheet
      }
    }
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy this link', url)
    }
  }

  return (
    <Button onClick={share} aria-label="Share this article">
      {copied ? <Check className="text-positive" /> : <Share2 />} {copied ? 'Link copied' : 'Share'}
    </Button>
  )
}
