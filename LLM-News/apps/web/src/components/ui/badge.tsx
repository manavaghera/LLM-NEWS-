import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium [&_svg]:size-3', {
  variants: {
    tone: {
      neutral: 'bg-sunken text-muted',
      positive: 'bg-positive/12 text-positive',
      negative: 'bg-negative/12 text-negative',
      accent: 'bg-accent-soft text-accent',
    },
  },
  defaultVariants: { tone: 'neutral' },
})

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
