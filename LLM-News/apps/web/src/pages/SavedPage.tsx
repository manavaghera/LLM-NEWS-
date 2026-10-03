import { Bookmark, X } from 'lucide-react'
import { Link } from 'react-router'
import { FollowButton, SaveButton } from '@/components/news/LibraryButtons'
import { ArticleImage, Kicker } from '@/components/news/parts'
import { EmptyState } from '@/components/ui/feedback'
import { categoryInfo, formatLongDate } from '@/lib/format'
import { library, useLibrary } from '@/lib/library'

function Following() {
  const lib = useLibrary()
  const topics = [
    ...lib.categories.map((c) => ({ key: `c:${c}`, label: categoryInfo(c).label, remove: () => library.toggleCategory(c) })),
    ...lib.keywords.map((k) => ({ key: `k:${k}`, label: `“${k}”`, remove: () => library.toggleKeyword(k) })),
  ]
  return (
    <section aria-labelledby="following" className="rounded-2xl border border-rule bg-surface p-5">
      <h2 id="following" className="font-semibold">Topics you follow</h2>
      {topics.length ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {topics.map((t) => (
            <li key={t.key}>
              <button type="button" onClick={t.remove} className="inline-flex items-center gap-1 rounded-full bg-sunken px-3 py-1 text-sm hover:text-negative"
                aria-label={`Stop following ${t.label}`}>
                {t.label} <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-muted">
          None yet. Follow a category on the front page, or a word from{' '}
          <Link to="/search" className="text-accent hover:underline">search</Link>. Matching stories appear in “For you”.
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2 text-sm text-muted">
        Categories:
        {['social', 'tech', 'entertainment'].map((c) => <FollowButton key={c} kind="category" value={c} label={categoryInfo(c).label} />)}
      </div>
    </section>
  )
}

export function SavedPage() {
  const lib = useLibrary()
  const dates = [...new Set(lib.saved.map((s) => s.date))].sort().reverse()

  return (
    <div className="space-y-10">
      <title>Saved · NewsSense</title>
      <h1 className="headline text-4xl font-semibold tracking-tight">Saved stories</h1>
      <Following />
      {!lib.saved.length ? (
        <EmptyState icon={<Bookmark />} title="Nothing saved yet">
          Use the bookmark on any story to keep it here. Saved stories stay in this browser.
        </EmptyState>
      ) : (
        dates.map((date) => (
          <section key={date} aria-labelledby={`saved-${date}`} className="space-y-4">
            <h2 id={`saved-${date}`} className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">{formatLongDate(date)}</h2>
            <ul className="divide-y divide-rule rounded-2xl border border-rule bg-surface">
              {lib.saved.filter((s) => s.date === date).map((s) => (
                <li key={`${s.date}/${s.group_id}`} className="flex items-center gap-4 p-4">
                  <ArticleImage src={s.image_url ?? ''} alt="" category={s.category} show={!!s.image_url} className="size-16 shrink-0 rounded-lg" />
                  <div className="min-w-0 flex-1">
                    <Kicker category={s.category} />
                    <Link to={`/article/${s.date}/${s.group_id}`} className="headline mt-0.5 block text-lg leading-snug hover:underline">
                      {s.headline}
                    </Link>
                    <p className="text-xs text-faint">Saved {new Date(s.saved_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}</p>
                  </div>
                  <SaveButton article={s} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
