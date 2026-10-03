import { ArrowLeft, FileQuestion } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, media } from '@/api/client'
import { useArticle } from '@/api/queries'
import type { Article } from '@/api/types'
import { ArticleSections, BottomLine, SourcesList, Timeline } from '@/components/article/ArticleBody'
import { AtAGlance } from '@/components/article/AtAGlance'
import { AudioPlayer } from '@/components/article/AudioPlayer'
import { CoverageComparison } from '@/components/article/CoverageComparison'
import { ShareButton } from '@/components/article/ShareButton'
import { TranslateControl } from '@/components/article/TranslateControl'
import { TrustNote } from '@/components/article/TrustNote'
import { useArticleChatScope } from '@/components/chat/ChatProvider'
import { SaveButton } from '@/components/news/LibraryButtons'
import { ArticleImage, Kicker } from '@/components/news/parts'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { useEdition, editionSearch } from '@/hooks/useEdition'
import { formatLongDate, publisherName } from '@/lib/format'

function ArticleSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-5" aria-busy>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-11 w-2/3" />
      <Skeleton className="aspect-[16/9] w-full rounded-2xl" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
    </div>
  )
}

export function ArticlePage() {
  const { date = '', groupId = '' } = useParams()
  const article = useArticle(date, groupId)
  const edition = useEdition()
  const [translation, setTranslation] = useState<{ key: string; article: Article } | null>(null)
  const key = `${date}/${groupId}`
  const shown = translation?.key === key ? translation.article : article.data

  useArticleChatScope(date, groupId, article.data?.headline)

  if (article.isLoading) return <ArticleSkeleton />
  if (article.error instanceof ApiError && article.error.status === 404) {
    return (
      <EmptyState icon={<FileQuestion />} title="Article not found">
        <Link to="/" className="font-medium text-accent hover:underline">Back to today&apos;s news</Link>
      </EmptyState>
    )
  }
  if (article.error || !shown) return <ErrorState title="Couldn't load this article" error={article.error} onRetry={() => article.refetch()} />

  return (
    <article>
      <title>{`${shown.headline} · NewsSense`}</title>
      <Link
        to={{ pathname: '/', search: editionSearch(date, edition.dates[0]) }}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
      >
        <ArrowLeft className="size-4" aria-hidden /> All stories
      </Link>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-8">
          <header className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Kicker category={shown.category} />
              <span className="text-xs text-faint">{formatLongDate(date)}</span>
            </div>
            <h1 className="headline text-4xl leading-[1.1] font-semibold sm:text-5xl">{shown.headline}</h1>
            {shown.subheadline && <p className="headline text-xl leading-relaxed text-muted italic">{shown.subheadline}</p>}
            <TrustNote article={shown} />
            <div className="flex flex-wrap items-center gap-3">
              {shown._translation ? (
                // Read aloud in the translation's language with a native voice (generated on first play)
                <AudioPlayer key={shown._translation.target_lang} lazy src={media.audioIn(date, groupId, shown._translation.target_lang)}
                  label={`Listen in ${shown._translation.target_lang_name}`} />
              ) : (
                <AudioPlayer key="en" src={media.audio(date, groupId)} />
              )}
              <TranslateControl
                date={date}
                groupId={groupId}
                translatedTo={shown._translation?.target_lang_name}
                onTranslated={(translated) => setTranslation({ key, article: translated })}
                onShowOriginal={() => setTranslation(null)}
              />
              <SaveButton article={{ date, group_id: groupId, headline: shown.headline, category: shown.category, image_url: shown.image_url }} />
              <ShareButton date={date} groupId={groupId} title={shown.headline} />
            </div>
          </header>

          <figure>
            <ArticleImage src={shown.image_url ?? media.image(date, groupId)} alt="" category={shown.category} priority className="aspect-[16/9] w-full rounded-2xl" />
            {shown.image_credit && (
              <figcaption className="mt-2 text-xs text-faint">Image: {publisherName(shown.image_credit)}</figcaption>
            )}
          </figure>

          {shown.lead && <p className="headline text-2xl leading-relaxed">{shown.lead}</p>}
          <ArticleSections article={shown} />
          <CoverageComparison coverage={shown.coverage} />
          <BottomLine text={shown.conclusion} />
          <Timeline timeline={shown.timeline} />
          <SourcesList article={shown} />
        </div>
        <AtAGlance article={shown} />
      </div>
    </article>
  )
}
