import type { Article } from '@/api/types'

export function uniqueSources(article: Article): string[] {
  return [...new Set(article.body.flatMap((section) => section.sources ?? []))]
}

/** "quick_news (OPENROUTER / qwen/qwen-plus)" -> "qwen/qwen-plus" */
export function writerModel(generatedBy?: string): string | null {
  const inside = generatedBy?.match(/\(([^)]*)\)/)?.[1]
  return inside?.split(' / ').slice(1).join(' / ') || null
}
