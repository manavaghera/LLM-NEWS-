import type {
  AccuracyResponse,
  Article,
  CategoryTrendsResponse,
  Correction,
  DatesResponse,
  DigestResponse,
  LanguagesResponse,
  ModelCatalog,
  ModelsResponse,
  NewsItem,
  NewsUpdateJob,
  Operations,
  PipelineUsage,
  PublisherDiversityResponse,
  RelatedItem,
  ReportRequest,
  ReaderReport,
  ReportStatus,
  SiteConfig,
  StoryUpdates,
  SentimentTrendsResponse,
  TopicsResponse,
  TranslateResponse,
  UpdateStatus,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The backend's error message (FastAPI puts it in `detail`), falling back to the HTTP status text. */
export async function readError(response: Response): Promise<ApiError> {
  let message = response.statusText || `Request failed (${response.status})`
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') message = body.detail
  } catch {
    // not JSON; keep the status text
  }
  return new ApiError(response.status, message)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, {
    ...init,
    headers,
  })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<T>
}

const adminHeaders = (token?: string) => token ? { 'X-Admin-Token': token } : undefined

const q = encodeURIComponent

export const api = {
  dates: () => request<DatesResponse>('/api/news/dates'),
  news: (date: string) => request<NewsItem[]>(`/api/news?date=${q(date)}`),
  modelCatalog: () => request<ModelCatalog>('/api/news/models/catalog'),
  search: (query: string) => request<NewsItem[]>(`/api/news/search?q=${q(query)}&limit=60`),
  article: (date: string, groupId: string) => request<Article>(`/api/news/articles/${q(date)}/${q(groupId)}`),
  topics: (days: number) => request<TopicsResponse>(`/api/trends/topics?days=${days}&top_n=12`),
  categoryTrends: (days: number) => request<CategoryTrendsResponse>(`/api/trends/categories?days=${days}`),
  sentimentTrends: (days: number) => request<SentimentTrendsResponse>(`/api/trends/sentiment?days=${days}`),
  publishers: (date: string) => request<PublisherDiversityResponse>(`/api/trends/publishers?date=${q(date)}`),
  digest: (date: string) => request<DigestResponse>(`/api/digest/daily/${q(date)}`),
  languages: () => request<LanguagesResponse>('/api/translate/languages'),
  translate: (date: string, groupId: string, language: string) =>
    request<TranslateResponse>('/api/translate/article', {
      method: 'POST',
      body: JSON.stringify({ date, group_id: groupId, target_languages: [language] }),
    }),
  models: () => request<ModelsResponse>('/api/chat/models'),
  related: (date: string, groupId: string) => request<RelatedItem[]>(`/api/news/articles/${q(date)}/${q(groupId)}/related`),
  storyUpdates: (date: string, groupId: string) => request<StoryUpdates>(`/api/news/articles/${q(date)}/${q(groupId)}/updates`),
  updateStatus: () => request<UpdateStatus>('/api/news/status'),
  config: () => request<SiteConfig>('/api/config'),
  pushSubscribe: (subscription: { endpoint: string; keys: { p256dh: string; auth: string } }, categories: string[], keywords: string[], managementToken?: string) =>
    request<{ status: string; management_token: string }>('/api/notifications/push', {
      method: 'POST', body: JSON.stringify({ ...subscription, categories, keywords, ...(managementToken ? { management_token: managementToken } : {}) }),
    }),
  pushUnsubscribe: (endpoint: string, managementToken: string) =>
    request<{ status: string }>('/api/notifications/push', {
      method: 'DELETE', body: JSON.stringify({ endpoint, management_token: managementToken }),
    }),
  accuracy: (days: number) => request<AccuracyResponse>(`/api/trends/accuracy?days=${days}`),
  report: (report: ReportRequest) =>
    request<{ status: string }>('/api/reports', { method: 'POST', body: JSON.stringify(report) }),
  corrections: (date: string, groupId: string) =>
    request<{ corrections: Correction[] }>(`/api/reports/corrections/${q(date)}/${q(groupId)}`),
  adminLogin: (token: string) => request<{ status: string; expires_in: number }>('/api/admin/login', { method: 'POST', body: JSON.stringify({ token }) }),
  adminAccountLogin: (username: string, password: string, otp = '') => request<{ status: string; expires_in: number; user?: { username: string; role: string; mfa_enabled: boolean } }>('/api/admin/login', {
    method: 'POST', body: JSON.stringify({ username, password, otp }),
  }),
  adminSession: () => request<{ authenticated: boolean }>('/api/admin/session'),
  adminLogout: () => request<{ status: string }>('/api/admin/logout', { method: 'POST' }),
  analytics: (event: 'page_view' | 'search' | 'article_saved' | 'story_followed' | 'topic_followed' | 'model_compared' | 'category_view' | 'return_visit' | 'onboarding_completed' | 'alert_enabled' | 'digest_opened', detail = '') =>
    request<{ status: string }>('/api/analytics/event', { method: 'POST', body: JSON.stringify({ event, detail }) }),
  operations: (token = '') => request<Operations>('/api/operations', { headers: adminHeaders(token) }),
  newsUpdate: (token = '') => request<{ job: NewsUpdateJob | null }>('/api/operations/update', { headers: adminHeaders(token) }),
  startNewsUpdate: (token = '') => request<{ job: NewsUpdateJob; created: boolean }>('/api/operations/update', {
    method: 'POST', headers: adminHeaders(token),
  }),
  budget: (token: string, dailyCallLimit: number, monthlyCallLimit?: number) => request<PipelineUsage>('/api/operations/budget', {
    method: 'PATCH', headers: adminHeaders(token), body: JSON.stringify({ daily_call_limit: dailyCallLimit, ...(monthlyCallLimit === undefined ? {} : { monthly_call_limit: monthlyCallLimit }) }),
  }),
  spendingBudget: (token: string, dailyUsd: number, monthlyUsd: number) => request<PipelineUsage>('/api/operations/spending', {
    method: 'PATCH', headers: adminHeaders(token), body: JSON.stringify({ daily_usd: dailyUsd, monthly_usd: monthlyUsd }),
  }),
  reports: (token = '') => request<{ reports: ReaderReport[] }>('/api/reports', { headers: adminHeaders(token) }),
  resolveReport: (token: string, id: number, status: ReportStatus, resolution: string) => request<{ report: ReaderReport }>(`/api/reports/${id}`, {
    method: 'PATCH', headers: adminHeaders(token), body: JSON.stringify({ status, resolution }),
  }),
  publishCorrection: (token: string, id: number, text: string) => request<{ status: string; correction: Correction }>(`/api/reports/${id}/correction`, {
    method: 'POST', headers: adminHeaders(token), body: JSON.stringify({ text }),
  }),
}

/** Public URLs the backend serves for each article's generated media. */
export const media = {
  image: (date: string, groupId: string) => `/static/images/${q(date)}/${q(groupId)}.jpg`,
  audio: (date: string, groupId: string) => `/static/audio/${q(date)}/${q(groupId)}.mp3`,
  /** Spoken summary in a language (translations must exist first; generated on first play) */
  audioIn: (date: string, groupId: string, lang: string) => `/api/audio/article/${q(date)}/${q(groupId)}/${q(lang)}`,
  briefing: (date: string) => `/api/digest/daily/${q(date)}/audio`,
  /** Link with preview tags for chat apps and social sites; forwards people to the article */
  share: (date: string, groupId: string) => `${window.location.origin}/share/${q(date)}/${q(groupId)}`,
}
