import { useMatch, useSearchParams } from 'react-router'
import { useDates } from '@/api/queries'

/** Article routes keep their edition; other pages use ?date= or the latest available edition. */
export function useEdition() {
  const [params] = useSearchParams()
  const article = useMatch('/article/:date/:groupId')
  const query = useDates()
  const dates = query.data?.dates ?? []
  const requested = article?.params.date ?? params.get('date')
  const date = requested && dates.includes(requested) ? requested : dates[0]

  return {
    date,
    dates,
    isLatest: date === dates[0],
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}

/** Search string that keeps the chosen edition when linking between pages. */
export function editionSearch(date: string | undefined, latest: string | undefined): string {
  return date && date !== latest ? `?date=${date}` : ''
}
