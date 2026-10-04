import { Newspaper, Scale, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import type { NewsItem } from '@/api/types'
import { categoryInfo, plural, publisherName } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Small uppercase category label above headlines. */
export function Kicker({ category, className }: { category: string; className?: string }) {
  const info = categoryInfo(category)
  return (
    <span className={cn('text-xs font-semibold uppercase tracking-[0.12em]', info.tone, className)}>{info.label}</span>
  )
}

/** Marks a story that an hourly update added. */
export function NewBadge() {
  return (
    <span className="rounded-full bg-accent px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-accent-ink">
      New
    </span>
  )
}

/** Article image; falls back to a category-tinted placeholder when missing or broken. */
export function ArticleImage({
  src,
  alt,
  category,
  show = true,
  className,
  priority = false,
}: {
  src: string
  alt: string
  category: string
  show?: boolean
  className?: string
  priority?: boolean
}) {
  const [failed, setFailed] = useState(false)
  const info = categoryInfo(category)

  if (!show || failed) {
    return (
      <div className={cn('relative grid place-items-center overflow-hidden bg-sunken', className)} aria-hidden>
        <div className={cn('absolute inset-0 opacity-15', info.bg)} />
        <Newspaper className={cn('relative size-10 opacity-60', info.tone)} />
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      onError={() => setFailed(true)}
      className={cn('bg-sunken object-cover', className)}
    />
  )
}

/** Small signals of how a story was checked: claim check passed, outlets compared */
export function TrustChips({ item }: { item: Pick<NewsItem, 'claim_check' | 'outlets_compared'> }) {
  const checked = item.claim_check?.checked
  const outlets = item.outlets_compared ?? 0
  if (!checked && outlets < 2) return null
  return (
    <p className="relative z-10 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
      {checked && (
        <span className="inline-flex items-center gap-1" title="Every sentence was checked against its sources">
          <ShieldCheck className="size-3.5 text-positive" aria-hidden /> Fact-checked
        </span>
      )}
      {outlets >= 2 && (
        <span className="inline-flex items-center gap-1">
          <Scale className="size-3.5 text-tech" aria-hidden /> {outlets} outlets compared
        </span>
      )}
    </p>
  )
}

/** "3 sources · BBC News, NPR" */
export function SourceLine({ count, publishers, className }: { count?: number; publishers?: string[]; className?: string }) {
  if (!count && !publishers?.length) return null
  const names = (publishers ?? []).map(publisherName)
  return (
    <p className={cn('text-xs text-faint', className)}>
      {count ? plural(count, 'source') : null}
      {count && names.length ? ' · ' : null}
      {names.slice(0, 3).join(', ')}
      {names.length > 3 ? ` +${names.length - 3}` : null}
    </p>
  )
}
