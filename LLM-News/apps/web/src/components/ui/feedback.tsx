import { CircleAlert, RotateCcw } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('shimmer rounded-md', className)} />
}

export function ErrorState({ title, error, onRetry }: { title: string; error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="mx-auto flex max-w-xl flex-col items-center gap-3 rounded-2xl border border-rule bg-surface px-6 py-10 text-center">
      <CircleAlert className="size-6 text-negative" aria-hidden />
      <p className="font-medium">{title}</p>
      <p className="text-sm text-muted">{message}</p>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          <RotateCcw /> Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-3 rounded-2xl border border-dashed border-rule px-6 py-12 text-center">
      <div className="text-faint [&_svg]:size-7">{icon}</div>
      <p className="headline text-2xl">{title}</p>
      {children && <div className="text-sm text-muted">{children}</div>}
    </div>
  )
}
