import { Moon, Sun } from 'lucide-react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { editionSearch, useEdition } from '@/hooks/useEdition'
import { formatShortDate } from '@/lib/format'
import { useLibrary } from '@/lib/library'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <span aria-hidden className="grid size-8 place-items-center rounded-lg bg-accent text-accent-ink">
        <svg viewBox="0 0 32 32" className="size-5" fill="currentColor">
          <path d="M9 23V9h2.6l6.8 9.4V9H21v14h-2.6l-6.8-9.4V23z" />
        </svg>
      </span>
      <span className="headline text-2xl font-semibold tracking-tight">NewsSense</span>
    </span>
  )
}

function EditionPicker() {
  const { date, dates } = useEdition()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  if (dates.length === 0 || !date) return null

  const onChange = (next: string) => {
    // Digest follows the edition; every other page goes to that day's front page
    navigate({ pathname: pathname === '/digest' ? '/digest' : '/', search: editionSearch(next, dates[0]) })
  }

  return (
    <label className="flex items-center gap-2 text-sm text-muted">
      <span className="sr-only lg:not-sr-only">Edition</span>
      <select
        value={date}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 w-36 rounded-full border border-rule bg-surface px-3 text-sm text-ink lg:w-auto"
      >
        {dates.map((d, i) => (
          <option key={d} value={d}>
            {i === 0 ? `${formatShortDate(d)} (latest)` : formatShortDate(d)}
          </option>
        ))}
      </select>
    </label>
  )
}

export function SiteHeader() {
  const { theme, toggle } = useTheme()
  const { date, dates } = useEdition()
  const search = editionSearch(date, dates[0])
  const savedCount = useLibrary().saved.length

  const links = [
    { to: { pathname: '/', search }, label: 'Today', end: true },
    { to: { pathname: '/digest', search }, label: 'Daily Digest', end: false },
    { to: { pathname: '/trends' }, label: 'Trends', end: false },
    { to: { pathname: '/search' }, label: 'Search', end: false },
    { to: { pathname: '/saved' }, label: savedCount ? `Saved (${savedCount})` : 'Saved', end: false },
  ]

  const nav = (className: string) => (
    <nav aria-label="Main" className={className}>
      {links.map((link) => (
        <NavLink
          key={link.label}
          to={link.to}
          end={link.end}
          className={({ isActive }) =>
            cn(
              'whitespace-nowrap border-b-2 py-1 text-sm font-medium transition-colors',
              isActive ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink',
            )
          }
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex h-16 items-center gap-3 sm:gap-6">
          <Link to={{ pathname: '/', search }} aria-label="NewsSense home">
            <Logo />
          </Link>
          {nav('hidden items-center gap-4 md:flex lg:gap-6')}
          <div className="ml-auto flex items-center gap-2">
            <EditionPicker />
            <Button variant="ghost" size="icon" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </Button>
          </div>
        </div>
        {nav('-mx-4 flex gap-6 overflow-x-auto px-4 pb-2 [scrollbar-width:none] md:hidden')}
      </div>
    </header>
  )
}
