import { Bookmark, BookmarkCheck, Check, Plus } from 'lucide-react'
import { library, useLibrary } from '@/lib/library'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface SaveTarget {
  date: string
  group_id: string
  headline: string
  category: string
  image_url?: string
}

/** Bookmark a story. "overlay" sits on a card image, above the card's full-card link. */
export function SaveButton({ article, variant = 'button' }: { article: SaveTarget; variant?: 'button' | 'overlay' }) {
  const lib = useLibrary()
  const saved = library.isSaved(lib, article.date, article.group_id)
  const label = saved ? 'Remove from saved' : 'Save for later'
  const toggle = () =>
    library.toggleSaved({
      date: article.date, group_id: article.group_id, headline: article.headline,
      category: article.category, image_url: article.image_url,
    })

  if (variant === 'overlay') {
    return (
      <button
        type="button"
        onClick={toggle}
        aria-pressed={saved}
        aria-label={label}
        title={label}
        className={cn(
          'absolute top-2 right-2 z-10 grid size-9 place-items-center rounded-full bg-surface/90 shadow-sm backdrop-blur transition',
          saved ? 'text-accent' : 'text-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100',
        )}
      >
        {saved ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}
      </button>
    )
  }
  return (
    <Button onClick={toggle} aria-pressed={saved} aria-label={label}>
      {saved ? <BookmarkCheck className="text-accent" /> : <Bookmark />} {saved ? 'Saved' : 'Save'}
    </Button>
  )
}

/** Follow a category or keyword; followed topics feed the "For you" row. */
export function FollowButton({ kind, value, label }: { kind: 'category' | 'keyword'; value: string; label?: string }) {
  const lib = useLibrary()
  const key = value.trim().toLowerCase()
  const following = (kind === 'category' ? lib.categories : lib.keywords).includes(key)
  const toggle = () => (kind === 'category' ? library.toggleCategory(value) : library.toggleKeyword(value))
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={following}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium normal-case tracking-normal transition-colors',
        following ? 'border-accent bg-accent-soft text-accent' : 'border-rule text-muted hover:text-ink',
      )}
    >
      {following ? <Check className="size-3" /> : <Plus className="size-3" />}
      {following ? 'Following' : 'Follow'}
      {label ? ` ${label}` : ''}
    </button>
  )
}
