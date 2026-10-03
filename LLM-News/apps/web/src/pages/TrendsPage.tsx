import { TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { useCategoryTrends, useDates, usePublishers, useSentimentTrends, useTopics } from '@/api/queries'
import { ChartCard, StatTile, useChartColors, seriesColor } from '@/components/trends/chartKit'
import { HorizontalBars, StackedColumns, ToneLines } from '@/components/trends/charts'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { categoryInfo, formatShortDate, publisherName, regionName } from '@/lib/format'

const RANGES = [7, 14, 30]

type Row = Record<string, string | number | null>

function toneLabel(value: number) {
  return value >= 0.15 ? 'Positive' : value <= -0.15 ? 'Negative' : 'Neutral'
}

/** Position of a -1..1 value on a small track, from a centre line (polarity, not magnitude). */
function ToneMeter({ value, color }: { value: number; color: string }) {
  const width = `${Math.min(Math.abs(value), 1) * 50}%`
  return (
    <div className="relative mt-3 h-1.5 rounded-full bg-sunken" aria-hidden>
      <span className="absolute top-[-3px] left-1/2 h-3 w-px bg-faint" />
      <span
        className="absolute top-0 h-full rounded-full"
        style={{ width, background: color, ...(value >= 0 ? { left: '50%' } : { right: '50%' }) }}
      />
    </div>
  )
}

export function TrendsPage() {
  const [days, setDays] = useState(7)
  const colors = useChartColors()
  const dates = useDates()
  const latest = dates.data?.dates[0]
  const topics = useTopics(days)
  const coverage = useCategoryTrends(days)
  const tone = useSentimentTrends(days)
  const publishers = usePublishers(latest)

  const loading = dates.isLoading || topics.isLoading || coverage.isLoading || tone.isLoading
  const error = dates.error ?? topics.error ?? coverage.error ?? tone.error ?? publishers.error

  const header = (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="headline text-4xl font-semibold tracking-tight">Trends</h1>
        <p className="mt-1 text-muted">What the news has been about, and how it has been covered.</p>
      </div>
      <label className="flex items-center gap-2 text-sm text-muted">
        Time range
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="h-9 rounded-full border border-rule bg-surface px-3 text-ink">
          {RANGES.map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
      </label>
    </div>
  )

  if (loading) {
    return (
      <div>
        {header}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>
        <Skeleton className="mt-6 h-80 rounded-2xl" />
      </div>
    )
  }
  if (error) return <div>{header}<ErrorState title="Couldn't load trends" error={error} /></div>
  if (!latest) {
    return (
      <div>
        {header}
        <EmptyState icon={<TrendingUp />} title="No news to analyse yet">Generate some articles first, then come back.</EmptyState>
      </div>
    )
  }

  const dayCount = Math.max(coverage.data?.total_dates ?? 0, tone.data?.total_dates ?? 0)
  const multiDay = dayCount > 1
  const byCategory = Array.isArray(coverage.data?.category_trends) ? {} : coverage.data?.category_trends ?? {}
  const categories = Object.keys(byCategory).map(categoryInfo)
  const coverageDates = [...new Set(Object.values(byCategory).flat().map((p) => p.date))].sort()
  const coverageRows: Row[] = coverageDates.map((date) => ({
    label: formatShortDate(date),
    ...Object.fromEntries(categories.map((c) => [c.value, byCategory[c.value]?.find((p) => p.date === date)?.count ?? 0])),
  }))
  const toneDays = [...(tone.data?.sentiment_trends ?? [])].sort((a, b) => a.date.localeCompare(b.date))
  const latestTone = toneDays.at(-1)?.categories ?? {}
  const toneRows: Row[] = toneDays.map((day) => ({
    label: formatShortDate(day.date),
    ...Object.fromEntries(categories.map((c) => [c.value, day.categories[c.value]?.avg_sentiment ?? null])),
  }))
  const topicRows = (topics.data?.trending_topics ?? []).map((t) => ({ name: t.keyword, value: t.total_count, growth: t.growth_pct }))
  const publisherRows = (publishers.data?.publishers ?? []).map((p) => ({ name: publisherName(p.name), value: p.count }))
  const lastCoverage = coverageRows.at(-1)
  const todayTotal = lastCoverage ? categories.reduce((sum, c) => sum + Number(lastCoverage[c.value] ?? 0), 0) : 0

  return (
    <div className="space-y-6">
      {header}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Stories on the latest day" value={todayTotal} note={formatShortDate(latest)} />
        <StatTile label="Days of news analysed" value={dayCount} note={`within the last ${days} days`} />
        <StatTile label="Publishers cited" value={publishers.data?.unique_publishers ?? publisherRows.length} note="on the latest day" />
        <StatTile label="Regions covered" value={publishers.data?.unique_regions ?? 0} note={(publishers.data?.regions ?? []).map((r) => regionName(r.name)).join(', ')} />
      </div>
      {!multiDay && (
        <p className="rounded-xl bg-sunken px-4 py-3 text-sm text-muted">
          Only one day of news so far. Charts over time appear once the news script has run on more than one day.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Most mentioned topics"
          subtitle="Keywords across headlines and article text"
          table={{
            columns: multiDay ? ['Keyword', 'Mentions', 'Growth'] : ['Keyword', 'Mentions'],
            rows: topicRows.map((r) => (multiDay ? [r.name, r.value, `${r.growth}%`] : [r.name, r.value])),
          }}
        >
          {topicRows.length ? <HorizontalBars data={topicRows} valueLabel="mentions" /> : <p className="text-sm text-muted">No topics yet.</p>}
        </ChartCard>

        <ChartCard
          title="Publishers cited"
          subtitle={`Sections citing each publisher · ${formatShortDate(latest)}`}
          table={{ columns: ['Publisher', 'Sections'], rows: publisherRows.map((r) => [r.name, r.value]) }}
        >
          {publisherRows.length ? <HorizontalBars data={publisherRows} valueLabel="sections" /> : <p className="text-sm text-muted">No publisher data.</p>}
        </ChartCard>
      </div>

      <ChartCard
        title="Coverage by category"
        subtitle={multiDay ? 'Stories per day' : `Stories on ${formatShortDate(latest)}`}
        table={{ columns: ['Day', ...categories.map((c) => c.label)], rows: coverageRows.map((r) => [String(r.label), ...categories.map((c) => Number(r[c.value] ?? 0))]) }}
      >
        {multiDay ? (
          <StackedColumns data={coverageRows} categories={categories} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-3">
            {categories.map((c) => (
              <div key={c.value} className="flex items-center gap-3 rounded-xl bg-sunken p-4">
                <span aria-hidden className="size-2.5 rounded-full" style={{ background: seriesColor(colors, c.value) }} />
                <span className="text-sm text-muted">{c.label}</span>
                <span className="ml-auto text-2xl font-semibold">{Number(coverageRows[0]?.[c.value] ?? 0)}</span>
              </div>
            ))}
          </div>
        )}
      </ChartCard>

      <ChartCard
        title="Tone by category"
        subtitle="Average tone of article sections, from -1 (negative) to +1 (positive)"
        table={{
          columns: ['Day', ...categories.map((c) => c.label)],
          rows: toneRows.map((r) => [String(r.label), ...categories.map((c) => { const v = r[c.value]; return typeof v === 'number' ? v.toFixed(2) : '–' })]),
        }}
      >
        {multiDay ? (
          <ToneLines data={toneRows} categories={categories} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-3">
            {categories.map((c) => {
              const value = latestTone[c.value]?.avg_sentiment
              return (
                <div key={c.value} className="rounded-xl bg-sunken p-4">
                  <p className="flex items-center gap-2 text-sm text-muted">
                    <span aria-hidden className="size-2.5 rounded-full" style={{ background: seriesColor(colors, c.value) }} />
                    {c.label}
                  </p>
                  {value === undefined ? (
                    <p className="mt-2 text-sm text-faint">No tone data</p>
                  ) : (
                    <>
                      <p className="mt-2 text-2xl font-semibold">
                        {toneLabel(value)} <span className="text-base font-normal text-muted">{value > 0 ? '+' : ''}{value.toFixed(2)}</span>
                      </p>
                      <ToneMeter value={value} color={value >= 0 ? colors['series-positive'] : colors['series-negative']} />
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </ChartCard>
    </div>
  )
}
