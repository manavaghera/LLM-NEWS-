import { ExternalLink, FileSearch } from 'lucide-react'
import type { ClaimCheck } from '@/api/types'
import { domainOf, safeUrl } from '@/lib/citations'
import { publisherName } from '@/lib/format'

/** Literal excerpts recorded by the pipeline, alongside the checked claims they support. */
export function ClaimEvidence({ check }: { check?: ClaimCheck }) {
  const evidence = check?.evidence ?? []
  return (
    <section aria-labelledby="claim-evidence" className="space-y-4 rounded-2xl border border-rule bg-surface p-6">
      <h2 id="claim-evidence" className="flex items-center gap-2 text-lg font-semibold"><FileSearch className="size-5 text-accent" aria-hidden /> Claim evidence</h2>
      <p className="text-sm text-muted">Compare checked statements with verbatim excerpts from the original reporting. Excerpts provide context; an AI check can still miss mistakes.</p>
      {evidence.length ? (
        <div className="divide-y divide-rule">
          {evidence.map((claim, i) => (
            <details key={`${claim.id}/${i}`} className="py-4">
              <summary className="cursor-pointer text-sm font-medium leading-relaxed">{claim.text}</summary>
              <div className="mt-3 space-y-4 border-l-2 border-accent/30 pl-4">
                <p className="text-xs text-faint">{claim.section_index === undefined ? claim.field.replaceAll('_', ' ') : `Section ${claim.section_index + 1} · ${claim.field}`}</p>
                {claim.sources.map((source, j) => {
                  const href = safeUrl(source.url)
                  return (
                    <figure key={`${source.url}/${j}`} className="space-y-2">
                      <blockquote className="whitespace-pre-wrap text-sm leading-relaxed">“{source.quote}”</blockquote>
                      <figcaption className="text-xs text-muted">
                        {href ? <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
                          {source.publisher ? publisherName(source.publisher) : domainOf(href)} <ExternalLink className="size-3" aria-hidden />
                        </a> : source.publisher || 'Source unavailable'}
                      </figcaption>
                    </figure>
                  )
                })}
              </div>
            </details>
          ))}
        </div>
      ) : <p className="text-sm text-faint">No sentence-level source excerpts were recorded for this article. The numbered citations and Sources list still link to its reporting.</p>}
    </section>
  )
}
