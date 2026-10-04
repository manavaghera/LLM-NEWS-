import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
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

export const useSiteConfig = () => useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: HOUR })

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

/** When the news was last updated and the next update is due. Checks every minute (every 20 seconds once
 * the update is due) and reloads the stories as soon as a new update has run. */
export function useUpdateStatus() {
  const client = useQueryClient()
  const status = useQuery({
    queryKey: ['update-status'],
    queryFn: api.updateStatus,
    refetchInterval: (query) => {
      const next = Date.parse(query.state.data?.next_update ?? '')
      return Number.isFinite(next) && next <= Date.now() ? 20_000 : 60_000
    },
  })
  const last = status.data?.last_update
  const seen = useRef(last)
  useEffect(() => {
    if (last && seen.current && last !== seen.current) {
      void client.invalidateQueries({ queryKey: ['news'] })
      void client.invalidateQueries({ queryKey: ['dates'] })
    }
    seen.current = last ?? seen.current
  }, [last, client])
  return status
}
