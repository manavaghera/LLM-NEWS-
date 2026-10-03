import { Link } from 'react-router'
import type { NewsItem } from '@/api/types'
import { cn } from '@/lib/utils'
import { SaveButton } from './LibraryButtons'
import { ArticleImage, Kicker, SourceLine, TrustChips } from './parts'

const articlePath = (item: NewsItem) => `/article/${item.date}/${item.group_id}`

export function StoryCard({ item, showCategory = true }: { item: NewsItem; showCategory?: boolean }) {
  return (
    <article className="group relative flex flex-col gap-3">
      <div className="relative">
        <ArticleImage
          src={item.thumb_url ?? item.image_url}
          alt=""
          category={item.category}
          show={item.has_image !== false}
          className="aspect-[16/10] w-full rounded-xl"
        />
        <SaveButton article={item} variant="overlay" />
      </div>
      <div className="flex flex-col gap-2">
        {showCategory && <Kicker category={item.category} />}
        <h3 className="headline text-xl leading-snug font-medium">
          <Link to={articlePath(item)} className="after:absolute after:inset-0 group-hover:underline decoration-1 underline-offset-4">
            {item.headline}
          </Link>
        </h3>
        <p className="line-clamp-3 text-sm leading-relaxed text-muted">{item.summary}</p>
        <SourceLine count={item.source_count} publishers={item.publishers} />
        <TrustChips item={item} />
      </div>
    </article>
  )
}

export function LeadStory({ item }: { item: NewsItem }) {
  return (
    <article className="group relative grid gap-6 border-b border-rule pb-10 md:grid-cols-[1.35fr_1fr] md:items-center">
      <div className="relative">
        <ArticleImage
          src={item.image_url}
          alt=""
          category={item.category}
          show={item.has_image !== false}
          priority
          className="aspect-[16/10] w-full rounded-2xl"
        />
        <SaveButton article={item} variant="overlay" />
      </div>
      <div className="flex flex-col gap-3">
        <Kicker category={item.category} />
        <h2 className="headline text-3xl leading-tight font-medium sm:text-4xl">
          <Link to={articlePath(item)} className="after:absolute after:inset-0 group-hover:underline decoration-1 underline-offset-4">
            {item.headline}
          </Link>
        </h2>
        {item.subheadline && <p className="headline text-lg text-muted italic">{item.subheadline}</p>}
        <p className="leading-relaxed text-muted">{item.summary}</p>
        <SourceLine count={item.source_count} publishers={item.publishers} className={cn('text-sm')} />
        <TrustChips item={item} />
      </div>
    </article>
  )
}

export function StorySkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <div className="shimmer aspect-[16/10] w-full rounded-xl" />
      <div className="shimmer h-3 w-20 rounded" />
      <div className="shimmer h-5 w-full rounded" />
      <div className="shimmer h-5 w-2/3 rounded" />
      <div className="shimmer h-3 w-1/2 rounded" />
    </div>
  )
}
