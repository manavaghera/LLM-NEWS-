import { History } from 'lucide-react'
import { Link } from 'react-router'
import { useRelated } from '@/api/queries'
import { Kicker } from '@/components/news/parts'
import { formatShortDate } from '@/lib/format'

/** Earlier articles about the same running story (shared names such as "UN Security Council") */
export function EarlierCoverage({ date, groupId }: { date: string; groupId: string }) {
  const related = useRelated(date, groupId)
  if (!related.data?.length) return null
  return (
    <section aria-labelledby="earlier" className="space-y-4">
      <h2 id="earlier" className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-muted">
        <History className="size-4" aria-hidden /> Earlier coverage
      </h2>
      <ol className="space-y-3 border-l border-rule pl-5">
        {related.data.map((item) => (
          <li key={`${item.date}/${item.group_id}`} className="space-y-1">
            <p className="flex items-center gap-2 text-xs text-faint">
              {formatShortDate(item.date)} <Kicker category={item.category} className="text-[0.65rem]" />
            </p>
            <Link to={`/article/${item.date}/${item.group_id}`} className="headline block text-lg leading-snug hover:text-accent hover:underline">
              {item.headline}
            </Link>
            {item.shared_topics.length > 0 && (
              <p className="text-xs text-muted">Also about: {item.shared_topics.join(', ')}</p>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
