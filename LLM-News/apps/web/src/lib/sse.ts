/**
 * Split a server-sent-events buffer into complete `data:` payloads.
 * Returns the parsed payloads and the unfinished tail to prepend to the next chunk.
 */
export function splitSSE(buffer: string): { payloads: string[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const payloads: string[] = []
  for (const block of blocks) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (data) payloads.push(data)
  }
  return { payloads, rest }
}
