import { ExternalLink, Scale } from 'lucide-react'
import type { Coverage } from '@/api/types'
import { domainOf, safeUrl } from '@/lib/citations'
import { publisherName, regionName } from '@/lib/format'

function Tone({ value }: { value: number }) {
  const label = value >= 0.15 ? 'Positive' : value <= -0.15 ? 'Negative' : 'Neutral'
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted">
        Tone: <span className="font-medium text-ink">{label}</span> ({value > 0 ? '+' : ''}{value.toFixed(2)})
      </p>
      <div className="relative h-1.5 rounded-full bg-paper" aria-hidden>
        <span className="absolute top-[-3px] left-1/2 h-3 w-px bg-faint" />
        <span
          className="absolute top-0 h-full rounded-full"
          style={{
            width: `${Math.min(Math.abs(value), 1) * 50}%`,
            background: value >= 0 ? 'var(--series-positive)' : 'var(--series-negative)',
            ...(value >= 0 ? { left: '50%' } : { right: '50%' }),
          }}
        />
      </div>
    </div>
  )
}

/** "How each outlet covered it": framing per publisher for multi-source stories */
export function CoverageComparison({ coverage }: { coverage?: Coverage }) {
  if (!coverage || coverage.perspectives.length < 2) return null
  return (
    <section aria-labelledby="coverage" className="space-y-5 rounded-2xl border border-rule bg-surface p-6">
      <div>
        <h2 id="coverage" className="flex items-center gap-2 text-lg font-semibold">
          <Scale className="size-5 text-tech" aria-hidden /> How each outlet covered it
        </h2>
        <p className="mt-1 text-xs text-muted">AI comparison based on {coverage.basis ?? "each outlet's headline and summary"}.</p>
      </div>
      {(coverage.common_ground || coverage.differences) && (
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {coverage.common_ground && (
            <div>
              <dt className="font-semibold">Common ground</dt>
              <dd className="mt-1 leading-relaxed text-muted">{coverage.common_ground}</dd>
            </div>
          )}
          {coverage.differences && (
            <div>
              <dt className="font-semibold">Where they differ</dt>
              <dd className="mt-1 leading-relaxed text-muted">{coverage.differences}</dd>
            </div>
          )}
        </dl>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {coverage.perspectives.map((p) => (
          <article key={p.publisher} className="space-y-3 rounded-xl bg-sunken p-4 text-sm">
            <header className="flex items-baseline justify-between gap-2">
              <h3 className="font-semibold">{publisherName(p.publisher)}</h3>
              {p.region && <span className="text-xs text-faint">{regionName(p.region)}</span>}
            </header>
            <p className="headline text-base leading-snug">{p.angle}</p>
            {p.emphasis && <p className="text-muted"><span className="font-medium text-ink">Emphasis:</span> {p.emphasis}</p>}
            <Tone value={p.tone} />
            {p.not_mentioned.length > 0 && (
              <p className="text-muted"><span className="font-medium text-ink">Doesn&apos;t mention:</span> {p.not_mentioned.join('; ')}</p>
            )}
            <ul className="flex flex-wrap gap-x-3 gap-y-1">
              {p.links.map((link, i) => {
                const href = safeUrl(link)
                return href ? (
                  <li key={link}>
                    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
                      {/* Several reports from one outlet are numbered so the links can be told apart */}
                      Read on {domainOf(href)}{p.links.length > 1 ? ` (${i + 1})` : ''} <ExternalLink className="size-3" aria-hidden />
                    </a>
                  </li>
                ) : null
              })}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}
