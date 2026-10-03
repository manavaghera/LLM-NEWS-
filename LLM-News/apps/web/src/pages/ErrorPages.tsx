import { FileQuestion } from 'lucide-react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'
import { EmptyState, ErrorState } from '@/components/ui/feedback'

export function NotFoundPage() {
  return (
    <EmptyState icon={<FileQuestion />} title="Page not found">
      <Link to="/" className="font-medium text-accent hover:underline">Go to today&apos;s news</Link>
    </EmptyState>
  )
}

export function RouteError() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFoundPage />
  return (
    <div className="px-4 py-16">
      <ErrorState title="Something went wrong on this page" error={error} onRetry={() => window.location.reload()} />
    </div>
  )
}
