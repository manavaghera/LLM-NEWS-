// Shapes returned by the FastAPI backend (apps/app). Most endpoints return plain dicts,
// so these are kept by hand in this one file.

export interface NewsItem {
  story_identity?: string
  content_version?: string
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
  /** When the update that added it ran (one time per run); missing on older editions */
  added_at?: string | null
}

export interface ModelSnapshot {
  id: string
  name: string
  provider: string
  status: string
  input_price: number
  output_price: number
  context_tokens: number
  max_output_tokens: number | null
  multimodal: boolean
  open_weights: boolean
  best_for: string[]
  notes: string
  source_url: string
  pricing_url: string
}

export interface ModelCatalog {
  updated_at: string
  currency: string
  price_unit: string
  methodology: string
  models: ModelSnapshot[]
}

/** Second AI pass that checked every sentence against the source items (pipeline/news_checks.py) */
export interface ClaimCheck {
  checked: boolean
  statements: number
  removed: { text: string; reason: string }[]
  model?: string
  basis?: string
  evidence?: ClaimEvidence[]
}

export interface ClaimEvidence {
  id: string
  text: string
  field: string
  section_index?: number
  sources: { url: string; publisher: string; quote: string }[]
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
  story_identity?: string
  content_version?: string
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

export interface StoryUpdates {
  date: string
  group_id: string
  content_version: string
  story_identity: string
  updates: RelatedItem[]
}

export type ReportKind = 'wrong_fact' | 'missing_context' | 'bad_source' | 'other'

export interface ReportRequest {
  date: string
  group_id: string
  kind: ReportKind
  message: string
}

export interface Correction {
  id: number
  created_at: string
  text: string
}

export type ReportStatus = 'open' | 'resolved' | 'dismissed'

export interface ReaderReport extends ReportRequest {
  original_headline?: string
  story_identity?: string
  article_matches?: boolean
  id: number
  created_at: string
  status: ReportStatus
  resolution: string
  resolved_at: string | null
}

export interface PipelineUsage {
  date: string
  month: string
  pipeline_calls: number
  pipeline_limit: number
  remaining: number | null
  monthly_calls: number
  monthly_limit: number
  monthly_remaining: number | null
  models: { provider: string; model: string; calls: number; failed: number; prompt_tokens: number; completion_tokens: number }[]
}

export interface Operations {
  held_stories?: { date: string; category: string; headline: string; reason: string; created_at: string }[]
  update: UpdateStatus & { ok: boolean | null }
  feeds: { publisher: string; url: string; category: string; ok: boolean; items: number; full_text_items: number; error: string | null; last_checked: string }[]
  runs: { started_at: string; finished_at: string | null; date: string; status: string; added: number; held_back: number; error: string | null }[]
  usage: PipelineUsage
  analytics: {
    days: number
    since: string
    privacy: string
    events: { event: string; count: number }[]
    breakdown: { event: string; detail: string; count: number }[]
    requests: { route: string; method: string; status_group: string; count: number; average_ms: number; max_ms: number }[]
  }
}

/** Last and next news update (pipeline/daily_update.py --interval); all null without a schedule */
export interface UpdateStatus {
  date: string | null
  last_update: string | null
  next_update: string | null
  interval_minutes: number | null
  added: number
  ok?: boolean | null
  stale?: boolean
  minutes_since_update?: number | null
}

/** Site settings the pages need (GET /api/config) */
export interface SiteConfig {
  contact_email: string
  contact_address: string
}
