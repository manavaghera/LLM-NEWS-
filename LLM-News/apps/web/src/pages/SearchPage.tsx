import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useSearch } from '@/api/queries'
import type { NewsItem } from '@/api/types'
import { FollowButton } from '@/components/news/LibraryButtons'
import { StoryCard, StorySkeleton } from '@/components/news/StoryCard'
import { EmptyState, ErrorState } from '@/components/ui/feedback'
import { formatLongDate, plural } from '@/lib/format'

function byDate(items: NewsItem[]): [string, NewsItem[]][] {
  const groups = new Map<string, NewsItem[]>()
  for (const item of items) groups.set(item.date, [...(groups.get(item.date) ?? []), item])
  return [...groups.entries()]
}

/** Search every edition; the query lives in the URL (?q=) so results can be shared. */
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const query = (params.get('q') ?? '').trim()
  const [draft, setDraft] = useState(query)
  const results = useSearch(query)

  // Update the URL shortly after typing stops
  useEffect(() => {
    const timer = setTimeout(() => {
      if (draft.trim() !== query) setParams(draft.trim() ? { q: draft.trim() } : {}, { replace: true })
    }, 350)
    return () => clearTimeout(timer)
  }, [draft, query, setParams])

  return (
    <div>
      <title>{query ? `${query} · Search · NewsSense` : 'Search · NewsSense'}</title>
      <h1 className="headline mb-6 text-4xl font-semibold tracking-tight">Search the archive</h1>
      <label className="relative mb-8 flex max-w-2xl items-center">
        <span className="sr-only">Search every edition</span>
        <Search className="pointer-events-none absolute left-4 size-5 text-faint" aria-hidden />
        <input
          type="search"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="People, places, topics, publishers…"
          className="h-12 w-full rounded-full border border-rule bg-surface pr-11 pl-12 text-base placeholder:text-faint"
        />
        {draft && (
          <button type="button" onClick={() => setDraft('')} className="absolute right-4 text-faint hover:text-ink" aria-label="Clear search">
            <X className="size-5" />
          </button>
        )}
      </label>

      {query.length < 2 ? (
        <p className="text-muted">Type at least two letters. Every edition is searched, newest first.</p>
      ) : results.isLoading ? (
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <StorySkeleton key={i} />)}</div>
      ) : results.error ? (
        <ErrorState title="Search failed" error={results.error} onRetry={() => results.refetch()} />
      ) : !results.data?.length ? (
        <EmptyState icon={<Search />} title={`Nothing found for “${query}”`}>
          <p className="mb-3">Try a shorter or different word.</p>
          <FollowButton kind="keyword" value={query} label={`“${query}”`} />
        </EmptyState>
      ) : (
        <div className="space-y-12">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
            <span>{plural(results.data.length, 'story')} mentioning “{query}”</span>
            <FollowButton kind="keyword" value={query} label={`“${query}”`} />
          </div>
          {byDate(results.data).map(([date, items]) => (
            <section key={date} aria-labelledby={`d-${date}`} className="space-y-6">
              <h2 id={`d-${date}`} className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">{formatLongDate(date)}</h2>
              <div className="grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((item) => <StoryCard key={`${item.date}/${item.group_id}`} item={item} />)}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
