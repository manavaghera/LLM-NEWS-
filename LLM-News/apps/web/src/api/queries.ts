import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { ReportRequest } from './types'

const HOUR = 60 * 60 * 1000

export const useDates = () => useQuery({ queryKey: ['dates'], queryFn: api.dates })

export const useNews = (date: string | undefined) =>
  useQuery({ queryKey: ['news', date], queryFn: () => api.news(date!), enabled: !!date })

export const useSearch = (query: string) =>
  useQuery({ queryKey: ['search', query], queryFn: () => api.search(query), enabled: query.trim().length >= 2 })

export const useArticle = (date: string | undefined, groupId: string | undefined) =>
  useQuery({
    queryKey: ['article', date, groupId],
    queryFn: () => api.article(date!, groupId!),
    enabled: !!date && !!groupId,
  })

export const useTopics = (days: number) => useQuery({ queryKey: ['trends', 'topics', days], queryFn: () => api.topics(days) })

export const useCategoryTrends = (days: number) =>
  useQuery({ queryKey: ['trends', 'categories', days], queryFn: () => api.categoryTrends(days) })

export const useSentimentTrends = (days: number) =>
  useQuery({ queryKey: ['trends', 'sentiment', days], queryFn: () => api.sentimentTrends(days) })

export const usePublishers = (date: string | undefined) =>
  useQuery({ queryKey: ['trends', 'publishers', date], queryFn: () => api.publishers(date!), enabled: !!date })

// Digests are written by the LLM (the backend caches them); never refetch in the background
export const useDigest = (date: string | undefined) =>
  useQuery({
    queryKey: ['digest', date],
    queryFn: () => api.digest(date!),
    enabled: !!date,
    staleTime: HOUR,
    retry: false,
  })

export const useLanguages = () => useQuery({ queryKey: ['languages'], queryFn: api.languages, staleTime: Infinity })

export const useModels = () => useQuery({ queryKey: ['models'], queryFn: api.models, staleTime: HOUR })

export const useTranslate = () =>
  useMutation({
    mutationFn: ({ date, groupId, language }: { date: string; groupId: string; language: string }) =>
      api.translate(date, groupId, language),
  })

export const useRelated = (date: string | undefined, groupId: string | undefined) =>
  useQuery({
    queryKey: ['related', date, groupId],
    queryFn: () => api.related(date!, groupId!),
    enabled: !!date && !!groupId,
  })

export const useAccuracy = (days: number) => useQuery({ queryKey: ['trends', 'accuracy', days], queryFn: () => api.accuracy(days) })

export const useReport = () => useMutation({ mutationFn: (report: ReportRequest) => api.report(report) })
