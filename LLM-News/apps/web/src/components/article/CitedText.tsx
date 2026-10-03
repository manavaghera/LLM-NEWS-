import { parseParagraphs, type Segment } from '@/lib/citations'
import { cn } from '@/lib/utils'

function Segments({ segments }: { segments: Segment[] }) {
  return segments.map((segment, i) =>
    segment.type === 'text' ? (
      <span key={i}>{segment.text}</span>
    ) : segment.href ? (
      <sup key={i} className="ml-0.5">
        <a
          href={segment.href}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded px-0.5 font-sans text-[0.7em] font-semibold text-accent no-underline hover:bg-accent-soft"
          aria-label={`Source ${segment.label} (opens in a new tab)`}
        >
          [{segment.label}]
        </a>
      </sup>
    ) : (
      <sup key={i} className="ml-0.5 font-sans text-[0.7em] text-faint">[{segment.label}]</sup>
    ),
  )
}

/** Article text with inline citation links, rendered as text (never as HTML). */
export function CitedText({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn('space-y-5', className)}>
      {parseParagraphs(content).map((segments, i) => (
        <p key={i}>
          <Segments segments={segments} />
        </p>
      ))}
    </div>
  )
}
