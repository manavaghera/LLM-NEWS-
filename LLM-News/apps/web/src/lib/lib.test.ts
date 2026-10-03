import { describe, expect, it } from 'vitest'
import { domainOf, parseCitations, parseParagraphs, safeUrl } from './citations'
import { categoryInfo, publisherName, reliabilityOf, sentimentOf } from './format'
import { parseInline, parseMarkdown } from './markdown'
import { splitSSE } from './sse'

describe('parseCitations', () => {
  it('splits text and numbered source links', () => {
    const html = "Five men were bailed.<a href='https://www.npr.org/a?x=1&amp;y=2'>[1]</a> Police said more.<a href=\"https://cbc.ca/b\">[2]</a>"
    expect(parseCitations(html)).toEqual([
      { type: 'text', text: 'Five men were bailed.' },
      { type: 'cite', label: '1', href: 'https://www.npr.org/a?x=1&y=2' },
      { type: 'text', text: ' Police said more.' },
      { type: 'cite', label: '2', href: 'https://cbc.ca/b' },
    ])
  })

  it('never keeps HTML or unsafe links', () => {
    const segments = parseCitations("<img src=x onerror=alert(1)>Hi <b>there</b><a href='javascript:alert(1)'>[3]</a>")
    expect(segments).toEqual([
      { type: 'text', text: 'Hi there' },
      { type: 'cite', label: '3', href: null },
    ])
  })

  it('splits paragraphs on blank lines', () => {
    expect(parseParagraphs('One.\n\nTwo.')).toHaveLength(2)
  })
})

describe('url helpers', () => {
  it('accepts only http(s)', () => {
    expect(safeUrl('https://bbc.co.uk/x')).toBe('https://bbc.co.uk/x')
    expect(safeUrl('data:text/html,hi')).toBeNull()
    expect(safeUrl('not a url')).toBeNull()
  })
  it('extracts a readable domain', () => {
    expect(domainOf('https://www.theguardian.com/world/x')).toBe('theguardian.com')
  })
})

describe('format', () => {
  it('names publishers readably', () => {
    expect(publisherName('BBCNews')).toBe('BBC News')
    expect(publisherName('TheGuardian')).toBe('The Guardian')
    expect(publisherName('NPR')).toBe('NPR')
  })
  it('labels sentiment and never invents reliability', () => {
    expect(sentimentOf({ section: '', content: '', sentisement_from_the_content: -0.6 })?.label).toBe('Negative')
    expect(sentimentOf({ section: '', content: '', sentisement_from_the_content: '0.05' })?.label).toBe('Neutral')
    expect(reliabilityOf({ section: '', content: '' })).toBeNull()
    expect(reliabilityOf({ section: '', content: '', fake_news_probability: 0.2 })?.label).toBe('High')
  })
  it('handles unknown categories', () => {
    expect(categoryInfo('tech').label).toBe('Technology')
    expect(categoryInfo('sport').label).toBe('Sport')
  })
})

describe('markdown', () => {
  it('parses lists, headings and inline styles', () => {
    const blocks = parseMarkdown('## Key points\n- **UN** extends mandate\n- Six months\n\n1. First\n2. Second')
    expect(blocks.map((b) => b.kind)).toEqual(['heading', 'list', 'list'])
    expect(parseInline('a **b** `c` *d*').map((p) => p.kind)).toEqual(['text', 'bold', 'text', 'code', 'text', 'italic'])
  })
  it('keeps HTML as plain text', () => {
    const [block] = parseMarkdown('<script>alert(1)</script>')
    expect(block).toEqual({ kind: 'paragraph', lines: [[{ kind: 'text', text: '<script>alert(1)</script>' }]] })
  })
})

describe('splitSSE', () => {
  it('returns complete events and keeps the unfinished tail', () => {
    const { payloads, rest } = splitSSE('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c"')
    expect(payloads).toEqual(['{"a":1}', '{"b":2}'])
    expect(rest).toBe('data: {"c"')
  })
  it('handles CRLF and keep-alive comments', () => {
    expect(splitSSE(': ping\r\n\r\ndata: x\r\n\r\n').payloads).toEqual(['x'])
  })
})
