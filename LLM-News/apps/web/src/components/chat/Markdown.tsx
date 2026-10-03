import { Link } from 'react-router'
import type { ChatSource } from '@/api/types'
import { safeUrl } from '@/lib/citations'
import { parseMarkdown, type Inline } from '@/lib/markdown'

const citeClass = 'rounded px-0.5 font-semibold text-accent no-underline hover:bg-accent-soft'

/** [n] in a reply: links to the article's source (new tab) or, for general questions, the story on this site */
function Citation({ label, sources }: { label: string; sources: ChatSource[] }) {
  const source = sources.find((s) => s.label === label)
  if (!source) return <sup className="text-faint">[{label}]</sup>
  const title = `Source ${label}: ${source.title}`
  if (/^\/article\/[\w-]+\/group_\d+$/.test(source.url)) {
    return <sup><Link to={source.url} className={citeClass} title={title}>[{label}]</Link></sup>
  }
  const href = safeUrl(source.url)
  return (
    <sup>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className={citeClass} title={title}>[{label}]</a>
      ) : (
        `[${label}]`
      )}
    </sup>
  )
}

function Inlines({ parts, sources }: { parts: Inline[]; sources: ChatSource[] }) {
  return parts.map((part, i) => {
    if (part.kind === 'cite') return <Citation key={i} label={part.text} sources={sources} />
    if (part.kind === 'bold') return <strong key={i} className="font-semibold">{part.text}</strong>
    if (part.kind === 'italic') return <em key={i}>{part.text}</em>
    if (part.kind === 'code') return <code key={i} className="rounded bg-sunken px-1 text-[0.9em]">{part.text}</code>
    return <span key={i}>{part.text}</span>
  })
}

/** Renders a chat reply's Markdown subset as React elements (no HTML injection); [n] become source links. */
export function Markdown({ source, sources = [] }: { source: string; sources?: ChatSource[] }) {
  return (
    <div className="space-y-2.5">
      {parseMarkdown(source).map((block, i) => {
        if (block.kind === 'heading') {
          return <p key={i} className="font-semibold"><Inlines parts={block.content} sources={sources} /></p>
        }
        if (block.kind === 'list') {
          const List = block.ordered ? 'ol' : 'ul'
          return (
            <List key={i} className={`space-y-1 pl-5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>
              {block.items.map((item, j) => <li key={j}><Inlines parts={item} sources={sources} /></li>)}
            </List>
          )
        }
        return (
          <p key={i}>
            {block.lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                <Inlines parts={line} sources={sources} />
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
