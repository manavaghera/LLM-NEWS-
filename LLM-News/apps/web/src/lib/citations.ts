// Article sections arrive as text with inline citations like
//   "...said on Monday.<a href='https://example.com/story'>[1]</a>"
// The text comes from news feeds and an LLM, so it is never rendered as HTML:
// it is split into plain text and citation segments, and only http(s) links survive.

export type Segment = { type: 'text'; text: string } | { type: 'cite'; label: string; href: string | null }

const CITATION = /<a\s[^>]*?href\s*=\s*(["'])(.*?)\1[^>]*>\s*\[(\d+)\]\s*<\/a>/gi
const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&#x27;': "'" }

export function decodeEntities(text: string): string {
  return text.replace(/&(amp|lt|gt|quot|#39|#x27);/g, (entity) => ENTITIES[entity] ?? entity)
}

export function safeUrl(raw: string): string | null {
  try {
    const url = new URL(decodeEntities(raw.trim()))
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}

function plainText(html: string): string {
  return decodeEntities(html.replace(/<[^>]*>/g, ''))
}

/** Split one paragraph into text and citation segments. */
export function parseCitations(content: string): Segment[] {
  const segments: Segment[] = []
  let last = 0
  for (const match of content.matchAll(CITATION)) {
    const before = plainText(content.slice(last, match.index))
    if (before) segments.push({ type: 'text', text: before })
    segments.push({ type: 'cite', label: match[3], href: safeUrl(match[2]) })
    last = match.index + match[0].length
  }
  const tail = plainText(content.slice(last))
  if (tail) segments.push({ type: 'text', text: tail })
  return segments
}

/** Paragraphs of a section's content, each already split into segments. */
export function parseParagraphs(content: string): Segment[][] {
  return content
    .split(/\n\s*\n/)
    .map((paragraph) => parseCitations(paragraph.trim()))
    .filter((segments) => segments.length > 0)
}

/** "https://www.bbc.co.uk/news/x" -> "bbc.co.uk" */
export function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
