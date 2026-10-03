import { ShieldCheck, TriangleAlert } from 'lucide-react'
import type { Article } from '@/api/types'
import { uniqueSources, writerModel } from '@/lib/article'
import { plural, publisherName } from '@/lib/format'

/** Who wrote the article from what, and what the claim check found */
export function TrustNote({ article }: { article: Article }) {
  const sources = uniqueSources(article).length
  const publishers = [...new Set(article.body.flatMap((s) => s.Publishers ?? []))].map(publisherName)
  const model = writerModel(article.generated_by)
  const check = article.claim_check

  return (
    <div className="space-y-2 rounded-xl bg-accent-soft/60 px-4 py-3 text-sm">
      <p className="flex items-start gap-2">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
        <span>
          <strong className="font-semibold">AI-written from {plural(sources, 'source')}</strong>
          {publishers.length > 0 && <> ({publishers.join(', ')})</>}
          {model && <> by {model}</>}. Numbers in brackets link to the original reporting.
        </span>
      </p>
      {check?.checked && (
        <div className="flex items-start gap-2">
          {check.removed.length ? (
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-negative" aria-hidden />
          ) : (
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden />
          )}
          <div>
            {check.removed.length ? (
              <>
                <strong className="font-semibold">Fact-checked:</strong>{' '}
                {plural(check.removed.length, 'statement')} of {check.statements} weren&apos;t supported by the sources and{' '}
                {check.removed.length === 1 ? 'was' : 'were'} removed.
                <details className="mt-1">
                  <summary className="cursor-pointer text-muted hover:text-ink">See what was removed</summary>
                  <ul className="mt-2 space-y-2">
                    {check.removed.map((r, i) => (
                      <li key={i} className="border-l-2 border-negative/40 pl-3">
                        <span className="line-through decoration-negative/60">{r.text}</span>
                        {r.reason && <span className="block text-xs text-muted">Why: {r.reason}</span>}
                      </li>
                    ))}
                  </ul>
                </details>
              </>
            ) : (
              <>
                <strong className="font-semibold">Fact-checked:</strong> all {check.statements} statements match the sources.
              </>
            )}
            <span className="block text-xs text-muted">Checked by a second AI pass against {check.basis ?? 'the sources'}.</span>
          </div>
        </div>
      )}
    </div>
  )
}
