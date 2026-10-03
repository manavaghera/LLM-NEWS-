import { ExternalLink } from 'lucide-react'
import type { Article, ArticleSection } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { uniqueSources } from '@/lib/article'
import { domainOf, safeUrl } from '@/lib/citations'
import { formatShortDate, publisherName, regionName, reliabilityOf, sentimentOf } from '@/lib/format'
import { CitedText } from './CitedText'

function SectionMeta({ section }: { section: ArticleSection }) {
  const sentiment = sentimentOf(section)
  const reliability = reliabilityOf(section)
  const publishers = section.Publishers ?? []
  const regions = section.Publisher_region_diversity ?? []
  if (!sentiment && !reliability && !publishers.length && !regions.length) return null

  return (
    <div className="flex flex-wrap items-center gap-2 font-sans">
      {sentiment && (
        <Badge tone={sentiment.tone === 'neutral' ? 'neutral' : sentiment.tone} title={`Tone score ${sentiment.value.toFixed(2)} (from -1 to 1)`}>
          {sentiment.label} tone
        </Badge>
      )}
      {reliability && (
        <Badge title={`Reliability ${(reliability.score * 100).toFixed(0)}% (${reliability.basis === 'classifier' ? 'fake-news classifier' : 'publisher trust rating'})`}>
          {reliability.basis === 'classifier' ? 'Reliability' : 'Publisher trust'}: {reliability.label}
        </Badge>
      )}
      {publishers.map((p) => (
        <Badge key={p}>{publisherName(p)}</Badge>
      ))}
      {regions.length > 0 && <span className="text-xs text-faint">{regions.map(regionName).join(' · ')}</span>}
    </div>
  )
}

export function ArticleSections({ article }: { article: Article }) {
  return (
    <div className="space-y-12">
      {article.body.map((section, i) => (
        <section key={i} className="space-y-4">
          {section.section && <h2 className="headline text-2xl font-semibold">{section.section}</h2>}
          <CitedText content={section.content} className="headline text-[1.18rem] leading-[1.75]" />
          <SectionMeta section={section} />
        </section>
      ))}
    </div>
  )
}

export function Timeline({ timeline }: { timeline?: Record<string, string> }) {
  const entries = Object.entries(timeline ?? {}).filter(([, text]) => text).sort(([a], [b]) => a.localeCompare(b))
  if (!entries.length) return null
  return (
    <section aria-labelledby="timeline" className="space-y-4">
      <h2 id="timeline" className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">Timeline</h2>
      <ol className="relative space-y-5 border-l border-rule pl-6">
        {entries.map(([date, text]) => (
          <li key={date} className="relative">
            <span className="absolute top-1.5 -left-[1.72rem] size-2.5 rounded-full border-2 border-paper bg-accent" aria-hidden />
            <p className="text-xs font-semibold text-accent">{formatShortDate(date)}</p>
            <p className="mt-1 text-[0.95rem] leading-relaxed">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

export function BottomLine({ text }: { text?: string }) {
  if (!text) return null
  return (
    <section aria-labelledby="bottom-line" className="rounded-2xl bg-sunken p-6">
      <h2 id="bottom-line" className="mb-2 text-sm font-semibold uppercase tracking-[0.14em] text-muted">The bottom line</h2>
      <p className="headline text-xl leading-relaxed">{text}</p>
    </section>
  )
}

export function SourcesList({ article }: { article: Article }) {
  const sources = uniqueSources(article)
  if (!sources.length) return null
  return (
    <section aria-labelledby="sources" className="space-y-4">
      <h2 id="sources" className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">Sources</h2>
      <ol className="space-y-2">
        {sources.map((source, i) => {
          const href = safeUrl(source)
          return (
            <li key={source} className="flex gap-3 text-sm">
              <span className="w-6 shrink-0 text-right font-semibold text-accent">{i + 1}.</span>
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer" className="group flex min-w-0 items-center gap-1.5 hover:text-accent">
                  <span className="font-medium">{domainOf(href)}</span>
                  <span className="truncate text-faint group-hover:text-accent">{href.replace(/^https?:\/\/(www\.)?/, '')}</span>
                  <ExternalLink className="size-3.5 shrink-0" aria-hidden />
                </a>
              ) : (
                <span className="text-muted">{source}</span>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
