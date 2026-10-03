import { Outlet, ScrollRestoration } from 'react-router'
import { ChatLauncher, ChatPanel } from '@/components/chat/ChatPanel'
import { SiteFooter } from './SiteFooter'
import { SiteHeader } from './SiteHeader'

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pt-8 sm:px-6">
        <Outlet />
      </main>
      <SiteFooter />
      <ChatLauncher />
      <ChatPanel />
      {/* Pages loaded directly all get the key "default", so key those by path: otherwise opening an
          article link restores the scroll position of whatever page was loaded before it */}
      <ScrollRestoration getKey={(location) => (location.key === 'default' ? location.pathname + location.search : location.key)} />

    </div>
  )
}
