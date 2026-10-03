import { MessageCircle, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Article } from '@/api/types'
import { useChat } from '@/components/chat/ChatProvider'
import { Button } from '@/components/ui/button'
import { publisherName, regionName, reliabilityOf, sentimentOf } from '@/lib/format'
import { uniqueSources, writerModel } from '@/lib/article'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-rule py-3 last:border-0">
      <dt className="text-xs uppercase tracking-wider text-faint">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

export function AtAGlance({ article }: { article: Article }) {
  const { setOpen } = useChat()
  const sources = uniqueSources(article)
  const publishers = [...new Set(article.body.flatMap((s) => s.Publishers ?? []))]
  const regions = [...new Set(article.body.flatMap((s) => s.Publisher_region_diversity ?? []))]
  const tones = article.body.map(sentimentOf).filter((s) => s !== null)
  const avgTone = tones.length ? tones.reduce((sum, t) => sum + t.value, 0) / tones.length : null
  const scores = article.body.map(reliabilityOf).filter((r) => r !== null)
  const model = writerModel(article.generated_by)

  return (
    <aside className="space-y-4 lg:sticky lg:top-24">
      <div className="rounded-2xl border border-rule bg-surface p-5">
        <p className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="size-4 text-accent" aria-hidden /> At a glance
        </p>
        <dl>
          <Row label="Sources">{sources.length}</Row>
          <Row label="Publishers">{publishers.length ? publishers.map(publisherName).join(', ') : 'Not listed'}</Row>
          {regions.length > 0 && <Row label="Regions">{regions.map(regionName).join(', ')}</Row>}
          {avgTone !== null && (
            <Row label="Overall tone">
              {avgTone >= 0.15 ? 'Positive' : avgTone <= -0.15 ? 'Negative' : 'Neutral'}{' '}
              <span className="text-faint">({avgTone.toFixed(2)})</span>
            </Row>
          )}
          <Row label="Reliability">
            {scores.length ? (
              <>
                {Math.round((scores.reduce((s, r) => s + r.score, 0) / scores.length) * 100)}%{' '}
                <span className="text-faint">
                  ({scores.some((r) => r.basis === 'classifier') ? 'fake-news classifier' : 'publisher trust ratings'})
                </span>
              </>
            ) : (
              <span className="text-muted">Not scored for this article</span>
            )}
          </Row>
          <Row label="Written by">{model ? <code className="text-xs">{model}</code> : 'AI model'}</Row>
        </dl>
      </div>
      <Button variant="primary" className="w-full" onClick={() => setOpen(true)}>
        <MessageCircle /> Ask about this article
      </Button>
    </aside>
  )
}
