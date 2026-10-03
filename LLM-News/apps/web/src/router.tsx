import { createBrowserRouter } from 'react-router'
import { Layout } from '@/components/layout/Layout'
import { ArticlePage } from '@/pages/ArticlePage'
import { DigestPage } from '@/pages/DigestPage'
import { NotFoundPage, RouteError } from '@/pages/ErrorPages'
import { HomePage } from '@/pages/HomePage'
import { SavedPage } from '@/pages/SavedPage'
import { SearchPage } from '@/pages/SearchPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'article/:date/:groupId', element: <ArticlePage /> },
      { path: 'digest', element: <DigestPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'saved', element: <SavedPage /> },
      // Loaded on demand: the charting library is most of the bundle
      { path: 'trends', lazy: () => import('@/pages/TrendsPage').then((m) => ({ Component: m.TrendsPage })) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
