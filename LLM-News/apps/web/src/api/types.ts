// Shapes returned by the FastAPI backend (apps/app). Most endpoints return plain dicts,
// so these are kept by hand in this one file.

export interface NewsItem {
  id: number
  group_id: string
  headline: string
  subheadline?: string
  category: string
  content: string
  summary: string
  date: string
  image_url: string
  has_image?: boolean
  image_credit?: string | null
  thumb_url?: string | null
  publishers?: string[]
  source_count?: number
  claim_check?: ClaimCheck | null
  outlets_compared?: number
}

/** Second AI pass that checked every sentence against the source items (pipeline/news_checks.py) */
export interface ClaimCheck {
  checked: boolean
  statements: number
  removed: { text: string; reason: string }[]
  model?: string
  basis?: string
}

/** How each outlet framed a story covered by several of them */
export interface Coverage {
  perspectives: {
    publisher: string
    region?: string
    angle: string
    tone: number
    emphasis: string
    not_mentioned: string[]
    links: string[]
  }[]
  common_ground: string
  differences: string
  basis?: string
}

export interface SourceItem {
  publisher: string
  region?: string
  title: string
  summary: string
  link: string
  published?: string
}

export interface ArticleSection {
  section: string
  content: string
  sources?: string[]
  sentisement_from_the_content?: number | string | null
  sentisement_from_the_posts_or_comments?: number | string | null
  fake_news_probability?: number | string | null
  date?: string
  Publisher_region_diversity?: string[]
  Publishers?: string[]
  publisher_reliability_score?: number | string | null
}

export interface Article {
  group_id: string
  category: string
  headline: string
  subheadline?: string
  lead?: string
  body: ArticleSection[]
  conclusion?: string
  timeline?: Record<string, string>
  summary_speech?: string
  generated_by?: string
  image_credit?: string
  image_source?: string
  image_url?: string
  claim_check?: ClaimCheck
  coverage?: Coverage
  source_items?: SourceItem[]
  _translation?: { source_lang: string; target_lang: string; target_lang_name: string }
}

export interface DatesResponse {
  dates: string[]
  total: number
}

export interface TrendingTopic {
  keyword: string
  total_count: number
  recent_count: number
  older_count: number
  growth_pct: number
}

export interface TopicsResponse {
  trending_topics: TrendingTopic[]
  total_dates: number
  date_range?: { from: string; to: string }
}

export interface CategoryTrendsResponse {
  category_trends: Record<string, { date: string; count: number }[]> | []
  total_dates: number
}

export interface SentimentTrendsResponse {
  sentiment_trends: {
    date: string
    categories: Record<string, { avg_sentiment: number; article_count: number }>
  }[]
  total_dates: number
}

export interface NamedCount {
  name: string
  count: number
}

export interface PublisherDiversityResponse {
  date?: string
  publishers: NamedCount[]
  regions: NamedCount[]
  total_articles: number
  unique_publishers?: number
  unique_regions?: number
}

export interface DigestResponse {
  date: string
  total_articles: number
  digest: string
  highlights: string[]
  // Written by the LLM, so the shape varies: a string, a list, or an object
  category_summary?: Record<string, unknown>
  trends?: unknown
  category_breakdown: Record<string, { count: number; headlines: string[] }>
  error?: boolean
}

export interface LanguagesResponse {
  languages: Record<string, string>
  total: number
}

export interface TranslateResponse {
  status: string
  language: string
  translation: Article
}

export interface ChatModel {
  name: string
  value: string
  provider: string
}

export interface ModelsResponse {
  models: ChatModel[]
  default: ChatModel | null
  total: number
}

/** A numbered source a chat answer can cite: an article's report, or (general questions) a story */
export interface ChatSource {
  label: string
  title: string
  url: string
}

export type ChatEvent =
  | { type: 'meta'; provider: string; model: string; sources?: ChatSource[] }
  | { type: 'delta'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface AccuracyDay {
  date: string
  articles: number
  checked: number
  statements: number
  removed: number
  removed_pct: number | null
  reader_reports?: number
}

export interface AccuracyResponse {
  days: AccuracyDay[]
  models: { writer: string; checker: string; articles: number; statements: number; removed: number; removed_pct: number | null }[]
}

export type RelatedItem = NewsItem & { shared_topics: string[] }

export type ReportKind = 'wrong_fact' | 'missing_context' | 'bad_source' | 'other'

export interface ReportRequest {
  date: string
  group_id: string
  kind: ReportKind
  message: string
}
