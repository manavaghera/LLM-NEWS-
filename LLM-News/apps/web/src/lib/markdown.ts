// A deliberately small Markdown subset for chat replies (paragraphs, lists, headings, **bold**,
// *italic*, `code`). It produces plain data that React renders as text, so model output can
// never inject HTML.

export type Inline = { kind: 'text' | 'bold' | 'italic' | 'code' | 'cite'; text: string }
export type Block =
  | { kind: 'paragraph'; lines: Inline[][] }
  | { kind: 'heading'; content: Inline[] }
  | { kind: 'list'; ordered: boolean; items: Inline[][] }

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\[\d{1,3}\])/g

export function parseInline(text: string): Inline[] {
  const parts: Inline[] = []
  for (const piece of text.split(INLINE)) {
    if (!piece) continue
    if (/^\[\d{1,3}\]$/.test(piece)) {
      parts.push({ kind: 'cite', text: piece.slice(1, -1) })
    } else if (piece.startsWith('**') && piece.endsWith('**') && piece.length > 4) {
      parts.push({ kind: 'bold', text: piece.slice(2, -2) })
    } else if (piece.startsWith('`') && piece.endsWith('`') && piece.length > 2) {
      parts.push({ kind: 'code', text: piece.slice(1, -1) })
    } else if (piece.startsWith('*') && piece.endsWith('*') && piece.length > 2) {
      parts.push({ kind: 'italic', text: piece.slice(1, -1) })
    } else {
      parts.push({ kind: 'text', text: piece })
    }
  }
  return parts
}

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const HEADING = /^\s*#{1,6}\s+(.*)$/

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = []
  let paragraph: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ kind: 'paragraph', lines: paragraph.map(parseInline) })
    paragraph = []
  }

  for (const line of source.replace(/\r\n/g, '\n').split('\n')) {
    const bullet = line.match(BULLET)
    const numbered = line.match(NUMBERED)
    const heading = line.match(HEADING)
    const listItem = bullet ?? numbered
    if (listItem) {
      flushParagraph()
      const ordered = !!numbered && !bullet
      const previous = blocks[blocks.length - 1]
      if (previous?.kind === 'list' && previous.ordered === ordered) previous.items.push(parseInline(listItem[1]))
      else blocks.push({ kind: 'list', ordered, items: [parseInline(listItem[1])] })
    } else if (heading) {
      flushParagraph()
      blocks.push({ kind: 'heading', content: parseInline(heading[1]) })
    } else if (!line.trim()) {
      flushParagraph()
    } else {
      paragraph.push(line.trim())
    }
  }
  flushParagraph()
  return blocks
}
