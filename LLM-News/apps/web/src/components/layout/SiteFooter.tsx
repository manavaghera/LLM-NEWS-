import { Rss, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import { Logo } from './SiteHeader'

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-rule">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.5fr_1fr]">
        <div className="space-y-3">
          <Logo />
          <p className="flex max-w-md gap-2 text-sm text-muted">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            Articles are written by AI from public news feeds. Every section links to the reporting it is based on,
            so you can always check the original source.
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted md:justify-end">
          <Link className="hover:text-ink" to="/">Today</Link>
          <Link className="hover:text-ink" to="/digest">Daily Digest</Link>
          <Link className="hover:text-ink" to="/trends">Trends</Link>
          <Link className="hover:text-ink" to="/saved">Saved</Link>
          {/* A real link: the feed is served by the backend, not the app */}
          <a className="inline-flex items-center gap-1 hover:text-ink" href="/feed.xml">
            <Rss className="size-3.5" aria-hidden /> RSS feed
          </a>
        </nav>
      </div>
    </footer>
  )
}
