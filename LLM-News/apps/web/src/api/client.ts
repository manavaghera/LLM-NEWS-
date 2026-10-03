import type {
  Article,
  CategoryTrendsResponse,
  DatesResponse,
  DigestResponse,
  LanguagesResponse,
  ModelsResponse,
  NewsItem,
  PublisherDiversityResponse,
  SentimentTrendsResponse,
  TopicsResponse,
  TranslateResponse,
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
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!response.ok) throw await readError(response)
  return response.json() as Promise<T>
}

const q = encodeURIComponent

export const api = {
  dates: () => request<DatesResponse>('/api/news/dates'),
  news: (date: string) => request<NewsItem[]>(`/api/news?date=${q(date)}`),
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
