import { Check, Copy, Newspaper, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useNews } from '@/api/queries'
import type { NewsItem } from '@/api/types'
import { FollowButton } from '@/components/news/LibraryButtons'
import { LeadStory, StoryCard, StorySkeleton } from '@/components/news/StoryCard'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState } from '@/components/ui/feedback'
import { useEdition } from '@/hooks/useEdition'
import { CATEGORIES, categoryInfo, formatLongDate, plural, publisherName } from '@/lib/format'
import { matchesFollows, useLibrary } from '@/lib/library'
import { cn } from '@/lib/utils'

const GENERATE_COMMAND = '.\\.venv\\Scripts\\python pipeline\\quick_news.py'

function matches(item: NewsItem, query: string) {
  const haystack = [item.headline, item.subheadline, item.summary, ...(item.publishers ?? []).map(publisherName)]
    .join(' ')
    .toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

function CategoryBar({ counts }: { counts: Record<string, number> }) {
  const [params, setParams] = useSearchParams()
  const active = params.get('category') ?? 'all'
  const query = params.get('q') ?? ''

  const update = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value && value !== 'all') next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: key === 'q' },
    )

  const tabs = [{ value: 'all', label: 'All' }, ...CATEGORIES.filter((c) => counts[c.value])]

  return (
    <div className="mb-8 flex flex-col gap-3 border-b border-rule pb-4 sm:flex-row sm:items-center sm:justify-between">
      <div role="group" aria-label="Filter by category" className="-mx-1 flex gap-1 overflow-x-auto px-1 [scrollbar-width:none]">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            type="button"
            aria-pressed={active === tab.value}
            onClick={() => update('category', tab.value)}
            className={cn(
              'whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors',
              active === tab.value ? 'bg-ink text-paper' : 'text-muted hover:bg-sunken hover:text-ink',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <label className="relative flex items-center sm:w-72">
        <span className="sr-only">Search today&apos;s stories</span>
        <Search className="pointer-events-none absolute left-3 size-4 text-faint" aria-hidden />
        <input
          type="search"
          value={query}
          onChange={(event) => update('q', event.target.value)}
          placeholder="Search stories and publishers"
          className="h-10 w-full rounded-full border border-rule bg-surface pr-9 pl-9 text-sm placeholder:text-faint"
        />
        {query && (
          <button type="button" onClick={() => update('q', '')} className="absolute right-3 text-faint hover:text-ink" aria-label="Clear search">
            <X className="size-4" />
          </button>
        )}
      </label>
    </div>
  )
}

function NoNewsYet() {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(GENERATE_COMMAND)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked; the command is still visible to copy by hand
    }
  }
  return (
    <EmptyState icon={<Newspaper />} title="No news yet">
      <p className="mb-4">Generate today&apos;s articles from public news feeds. In PowerShell, from the LLM-News folder:</p>
      <div className="flex items-center gap-2 rounded-xl bg-sunken p-2 pl-4 text-left">
        <code className="flex-1 overflow-x-auto font-mono text-xs text-ink">{GENERATE_COMMAND}</code>
        <Button size="sm" onClick={copy} aria-label="Copy command">
          {copied ? <Check /> : <Copy />} {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <p className="mt-4">Takes about two minutes. This page updates when you reload it.</p>
    </EmptyState>
  )
}

function Grid({ items, showCategory = true }: { items: NewsItem[]; showCategory?: boolean }) {
  return (
    <div className="grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <StoryCard key={item.group_id} item={item} showCategory={showCategory} />
      ))}
    </div>
  )
}

function LoadingFront() {
  return (
    <div className="space-y-12" aria-busy>
      <div className="grid gap-6 md:grid-cols-[1.35fr_1fr]">
        <div className="shimmer aspect-[16/10] rounded-2xl" />
        <div className="space-y-3 self-center">
          <div className="shimmer h-3 w-24 rounded" />
          <div className="shimmer h-9 w-full rounded" />
          <div className="shimmer h-9 w-3/4 rounded" />
          <div className="shimmer h-4 w-full rounded" />
        </div>
      </div>
      <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => <StorySkeleton key={i} />)}
      </div>
    </div>
  )
}

export function HomePage() {
  const edition = useEdition()
  const news = useNews(edition.date)
  const [params] = useSearchParams()
  const category = params.get('category') ?? 'all'
  const query = (params.get('q') ?? '').trim()

  const items = useMemo(() => news.data ?? [], [news.data])
  const counts = useMemo(
    () => items.reduce<Record<string, number>>((acc, item) => ({ ...acc, [item.category]: (acc[item.category] ?? 0) + 1 }), {}),
    [items],
  )

  if (edition.isLoading || (edition.date && news.isLoading)) return <LoadingFront />
  if (edition.error) return <ErrorState title="Couldn't reach the news server" error={edition.error} onRetry={() => edition.refetch()} />
  if (!edition.date) return <NoNewsYet />
  if (news.error) return <ErrorState title="Couldn't load today's stories" error={news.error} onRetry={() => news.refetch()} />
  if (items.length === 0) return <NoNewsYet />

  const filtered = items.filter((item) => (category === 'all' || item.category === category) && (!query || matches(item, query)))
  const filtering = category !== 'all' || !!query

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="headline text-4xl font-semibold tracking-tight">{edition.isLatest ? "Today's news" : 'News archive'}</h1>
        <p className="text-sm text-muted">
          {formatLongDate(edition.date)} · {plural(items.length, 'story')}
        </p>
      </div>
      <CategoryBar counts={counts} />

      {filtering ? (
        filtered.length ? (
          <section aria-label="Results" className="space-y-6">
            <p className="text-sm text-muted">
              {plural(filtered.length, 'story')}
              {category !== 'all' && ` in ${categoryInfo(category).label}`}
              {query && ` matching “${query}”`}
            </p>
            <Grid items={filtered} showCategory={category === 'all'} />
            {query && <ArchiveLink query={query} />}
          </section>
        ) : (
          <EmptyState icon={<Search />} title="No matching stories">
            <p>Try another word or category.</p>
            {query && <ArchiveLink query={query} />}
          </EmptyState>
        )
      ) : (
        <FrontPage items={items} />
      )}
    </div>
  )
}

function ArchiveLink({ query }: { query: string }) {
  return (
    <p className="mt-3 text-sm">
      <Link to={`/search?q=${encodeURIComponent(query)}`} className="font-medium text-accent hover:underline">
        Search every edition for “{query}” →
      </Link>
    </p>
  )
}

function FrontPage({ items }: { items: NewsItem[] }) {
  const lib = useLibrary()
  const following = lib.categories.length + lib.keywords.length > 0
  const lead = items.find((item) => item.has_image !== false && (item.source_count ?? 0) > 1) ?? items.find((item) => item.has_image !== false) ?? items[0]
  const rest = items.filter((item) => item !== lead)
  const known = CATEGORIES.map((c) => c.value as string)
  const sections = [
    ...CATEGORIES.map((c) => ({ key: c.value as string, title: c.section, items: rest.filter((i) => i.category === c.value) })),
    { key: 'other', title: 'More news', items: rest.filter((i) => !known.includes(i.category)) },
  ].filter((section) => section.items.length > 0)

  const forYou = following ? items.filter((item) => item !== lead && matchesFollows(item, lib)).slice(0, 6) : []

  return (
    <div className="space-y-14">
      <LeadStory item={lead} />
      {forYou.length > 0 && (
        <section aria-labelledby="for-you" className="space-y-6 rounded-2xl bg-sunken p-6">
          <h2 id="for-you" className="flex items-center justify-between gap-3 text-sm font-semibold uppercase tracking-[0.14em]">
            For you
            <Link to="/saved" className="text-xs font-medium normal-case tracking-normal text-muted hover:text-ink">Manage topics</Link>
          </h2>
          <Grid items={forYou} />
        </section>
      )}
      {sections.map((section) => (
        <section key={section.key} aria-labelledby={`section-${section.key}`} className="space-y-6">
          <h2 id={`section-${section.key}`} className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.14em]">
            <span className={cn('size-2 rounded-full', categoryInfo(section.key).bg)} aria-hidden />
            {section.title}
            {section.key !== 'other' && <FollowButton kind="category" value={section.key} />}
          </h2>
          <Grid items={section.items} showCategory={section.key === 'other'} />
        </section>
      ))}
    </div>
  )
}
