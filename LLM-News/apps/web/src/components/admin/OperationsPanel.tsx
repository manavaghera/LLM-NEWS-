import { RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { NewsUpdateJob, Operations, PipelineUsage } from '@/api/types'
import { Button } from '@/components/ui/button'

const timestamp = (value?: string | null) => value ? new Date(value).toLocaleString() : 'Not recorded'

const activeUpdate = (job: NewsUpdateJob | null) => job?.status === 'queued' || job?.status === 'running'

const formatRemaining = (seconds: number | null) => {
  if (seconds === null) return 'Estimating time remaining…'
  if (seconds <= 0) return 'Finishing the current step…'
  const minutes = Math.ceil(seconds / 60)
  if (minutes < 60) return `About ${minutes} min left`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return `About ${hours} hr${hours === 1 ? '' : 's'}${rest ? ` ${rest} min` : ''} left`
}

export function OperationsPanel({ data, token, onBudget, onRefresh }: { data: Operations; token: string; onBudget: (usage: PipelineUsage) => void; onRefresh?: () => void }) {
  const [draftLimit, setLimit] = useState<string | null>(null)
  const [draftMonthlyLimit, setMonthlyLimit] = useState<string | null>(null)
  const [draftDailySpend, setDailySpend] = useState<string | null>(null)
  const [draftMonthlySpend, setMonthlySpend] = useState<string | null>(null)
  const limit = draftLimit ?? String(data.usage.pipeline_limit)
  const monthlyLimit = draftMonthlyLimit ?? String(data.usage.monthly_limit)
  const dailySpend = draftDailySpend ?? String(data.usage.daily_spend_limit_usd)
  const monthlySpend = draftMonthlySpend ?? String(data.usage.monthly_spend_limit_usd)
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)
  const [updateFeedback, setUpdateFeedback] = useState<{ error: boolean; message: string } | null>(null)
  const [newsJob, setNewsJob] = useState<NewsUpdateJob | null>(data.news_update)
  const [clock, setClock] = useState(0)
  const updateActive = activeUpdate(newsJob)
  // The job is also polled below. This synchronization covers a manual dashboard refresh
  // and updates started in another administrator session.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { setNewsJob(data.news_update) }, [data.news_update])
  useEffect(() => {
    if (!updateActive) return
    const timer = window.setInterval(() => setClock(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [updateActive])
  useEffect(() => {
    if (!updateActive) return
    let cancelled = false
    const poll = async () => {
      try {
        const result = await api.newsUpdate(token)
        if (cancelled) return
        setNewsJob(result.job)
        if (result.job && !activeUpdate(result.job)) onRefresh?.()
      } catch {
        // The regular dashboard refresh still reports errors; keep the last visible progress here.
      }
    }
    const timer = window.setInterval(() => { void poll() }, 2_000)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [newsJob?.id, newsJob?.status, onRefresh, token, updateActive])
  const remaining = useMemo(() => {
    const progress = newsJob?.progress
    if (!progress) return null
    const estimate = progress.estimated_seconds_remaining
    if (estimate === null || estimate === undefined) return null
    const updated = progress.updated_at ? new Date(progress.updated_at).getTime() : clock
    return Math.max(0, estimate - Math.max(0, Math.floor((clock - updated) / 1_000)))
  }, [clock, newsJob])
  const startUpdate = async () => {
    setPending(true)
    setUpdateFeedback(null)
    try {
      const result = await api.startNewsUpdate(token)
      setNewsJob(result.job)
      setUpdateFeedback({ error: false, message: result.created ? 'News update queued.' : 'The existing news update is still running.' })
    } catch (error) {
      setUpdateFeedback({ error: true, message: error instanceof Error ? error.message : 'Could not start the news update.' })
    } finally { setPending(false) }
  }
  const save = async () => {
    const value = Number(limit)
    const monthlyValue = Number(monthlyLimit)
    if (!limit.trim() || !Number.isInteger(value) || value < 0 || value > 100000 ||
        !monthlyLimit.trim() || !Number.isInteger(monthlyValue) || monthlyValue < 0 || monthlyValue > 2000000) {
      setFeedback({ error: true, message: 'Enter valid whole-number daily and monthly limits.' })
      return
    }
    setPending(true)
    try {
      onBudget(await api.budget(token, value, monthlyValue))
      setLimit(null)
      setMonthlyLimit(null)
      setFeedback({ error: false, message: 'Pipeline limits saved.' })
    } catch (error) {
      setFeedback({ error: true, message: error instanceof Error ? error.message : 'Could not save the limit.' })
    } finally { setPending(false) }
  }
  const saveSpending = async () => {
    const daily = Number(dailySpend)
    const monthly = Number(monthlySpend)
    if (!dailySpend.trim() || !monthlySpend.trim() || !Number.isFinite(daily) || !Number.isFinite(monthly) ||
        daily < 0 || monthly < 0 || daily > 1000000 || monthly > 1000000) {
      setFeedback({ error: true, message: 'Enter valid daily and monthly USD limits.' })
      return
    }
    setPending(true)
    try {
      onBudget(await api.spendingBudget(token, daily, monthly))
      setDailySpend(null)
      setMonthlySpend(null)
      setFeedback({ error: false, message: 'Currency limits saved.' })
    } catch (error) {
      setFeedback({ error: true, message: error instanceof Error ? error.message : 'Could not save currency limits.' })
    } finally { setPending(false) }
  }
  return (
    <div className="space-y-8">
      <section aria-labelledby="pipeline-health" className="rounded-2xl border border-rule bg-surface p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div><h2 id="pipeline-health" className="text-lg font-semibold">Pipeline health</h2><p className="text-sm text-muted">Publish a quick AI Models update in about 2–3 minutes. The hourly schedule still runs the complete verified edition.</p></div>
          <Button variant="primary" onClick={() => { void startUpdate() }} disabled={pending || updateActive}>
            <RefreshCw className={updateActive ? 'animate-spin' : ''} />
            {updateActive ? 'Updating AI news…' : 'Quick AI news update'}
          </Button>
        </div>
        <dl className="grid gap-4 text-sm sm:grid-cols-3">
          <div><dt className="text-muted">Latest update</dt><dd>{timestamp(data.update.last_update)}</dd></div>
          <div><dt className="text-muted">Next update</dt><dd>{timestamp(data.update.next_update)}</dd></div>
          <div><dt className="text-muted">Latest update status</dt><dd className={data.update.ok === null ? 'text-muted' : data.update.ok ? 'text-positive' : 'text-negative'}>{data.update.ok === null ? 'Not recorded' : data.update.ok ? 'Healthy' : 'Needs attention'} · {data.update.added} added</dd></div>
        </dl>
        {newsJob && <div aria-live="polite" className="mt-5 rounded-xl border border-rule bg-paper p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="font-medium capitalize">{(newsJob.progress.phase || newsJob.status).replaceAll('_', ' ')}{newsJob.progress.category ? ` · ${newsJob.progress.category.replaceAll('_', ' ')}` : ''}</p>
            <p className="text-muted">{updateActive ? formatRemaining(remaining) : newsJob.status === 'succeeded' ? 'Update complete' : newsJob.status === 'failed' ? 'Update failed' : newsJob.status}</p>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-label="News update progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(newsJob.progress.percent ?? 0)}>
            <div className={`h-full rounded-full bg-accent transition-[width] duration-1000 ease-out ${updateActive ? 'animate-pulse' : ''}`} style={{ width: `${Math.min(100, Math.max(0, newsJob.progress.percent ?? 0))}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-faint">
            <span>{newsJob.progress.completed_categories !== null && newsJob.progress.completed_categories !== undefined && newsJob.progress.total_categories ? `${newsJob.progress.completed_categories} of ${newsJob.progress.total_categories} categories` : `Started ${timestamp(newsJob.created_at)}`}</span>
            <span>{Math.round(newsJob.progress.percent ?? 0)}%</span>
          </div>
          {newsJob.status === 'failed' && <p role="alert" className="mt-3 text-sm text-negative">The update failed. The previous published edition is still available.</p>}
        </div>}
        {updateFeedback && <p role={updateFeedback.error ? 'alert' : 'status'} className={`mt-3 text-sm ${updateFeedback.error ? 'text-negative' : 'text-positive'}`}>{updateFeedback.message}</p>}
      </section>
      <section aria-labelledby="pipeline-budget" className="space-y-4 rounded-2xl border border-rule bg-surface p-5">
        <h2 id="pipeline-budget" className="text-lg font-semibold">AI usage & spending protection</h2>
        <p className="text-sm text-muted">{data.usage.pipeline_calls} calls today · {data.usage.pipeline_limit ? `${data.usage.remaining ?? 0} remaining today` : 'No daily limit'} · {data.usage.monthly_calls} calls in {data.usage.month} · {data.usage.monthly_limit ? `${data.usage.monthly_remaining ?? 0} remaining this month` : 'No monthly limit'}. Generation pauses before either cap is exceeded.</p>
        <p className="text-sm text-muted">${data.usage.daily_spent_usd.toFixed(4)} spent today of ${data.usage.daily_spend_limit_usd.toFixed(2)} · ${data.usage.monthly_spent_usd.toFixed(4)} spent this month of ${data.usage.monthly_spend_limit_usd.toFixed(2)}. Unpriced calls are highlighted below.</p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-sm">Daily call limit (0 removes the limit)
            <input type="number" min={0} max={100000} step={1} value={limit} onChange={(e) => setLimit(e.target.value)} className="block h-10 w-48 rounded-xl border border-rule bg-paper px-3" />
          </label>
          <label className="space-y-1 text-sm">Monthly call limit (0 removes the limit)
            <input type="number" min={0} max={2000000} step={1} value={monthlyLimit} onChange={(e) => setMonthlyLimit(e.target.value)} className="block h-10 w-48 rounded-xl border border-rule bg-paper px-3" />
          </label>
          <Button onClick={() => { void save() }} disabled={pending}>{pending ? 'Saving…' : 'Save limits'}</Button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-sm">Daily spending limit (USD; 0 removes it)
            <input type="number" min={0} max={1000000} step="0.01" value={dailySpend} onChange={(e) => setDailySpend(e.target.value)} className="block h-10 w-48 rounded-xl border border-rule bg-paper px-3" />
          </label>
          <label className="space-y-1 text-sm">Monthly spending limit (USD; 0 removes it)
            <input type="number" min={0} max={1000000} step="0.01" value={monthlySpend} onChange={(e) => setMonthlySpend(e.target.value)} className="block h-10 w-48 rounded-xl border border-rule bg-paper px-3" />
          </label>
          <Button onClick={() => { void saveSpending() }} disabled={pending}>{pending ? 'Saving…' : 'Save spending limits'}</Button>
        </div>
        {feedback && <p role={feedback.error ? 'alert' : 'status'} className={`text-sm ${feedback.error ? 'text-negative' : 'text-positive'}`}>{feedback.message}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm"><caption className="sr-only">AI calls by model</caption>
            <thead><tr>{['Provider / model', 'Calls', 'Failed', 'Input tokens', 'Output tokens', 'Spent', 'Unpriced'].map((name) => <th key={name} scope="col" className="border-b border-rule p-2 font-medium">{name}</th>)}</tr></thead>
            <tbody>{data.usage.models.map((model) => <tr key={`${model.provider}/${model.model}`}>
              <th scope="row" className="p-2 font-normal">{model.provider} / {model.model}</th>
              {[model.calls, model.failed, model.prompt_tokens, model.completion_tokens].map((value, i) => <td key={i} className="p-2 tabular-nums">{value}</td>)}
              <td className="p-2 tabular-nums">${model.spent_usd.toFixed(4)}</td>
              <td className={model.unpriced_calls ? 'p-2 tabular-nums text-negative' : 'p-2 tabular-nums'}>{model.unpriced_calls}</td>
            </tr>)}</tbody>
          </table>
          {!data.usage.models.length && <p className="py-3 text-sm text-faint">No AI calls recorded yet.</p>}
        </div>
      </section>
      <section aria-labelledby="audience-health" className="space-y-4 rounded-2xl border border-rule bg-surface p-5">
        <div><h2 id="audience-health" className="text-lg font-semibold">Privacy-safe analytics</h2><p className="text-sm text-muted">{data.analytics.privacy}</p></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.analytics.events.slice(0, 8).map((item) => <div key={item.event} className="rounded-xl border border-rule p-3"><p className="text-xs uppercase tracking-wide text-faint">{item.event.replaceAll('_', ' ')}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{item.count}</p></div>)}
          {!data.analytics.events.length && <p className="text-sm text-muted">No reader events recorded yet.</p>}
        </div>
        {!!data.analytics.breakdown?.length && <div><h3 className="text-sm font-semibold">Popular categories and compared models</h3><div className="mt-2 flex flex-wrap gap-2">{data.analytics.breakdown.slice(0, 12).map((item) => <span key={`${item.event}/${item.detail}`} className="rounded-full bg-sunken px-3 py-1 text-xs">{item.detail.replaceAll('_', ' ')} · {item.count}</span>)}</div></div>}
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Slow and failed API routes</caption><thead><tr>{['Route', 'Status', 'Requests', 'Average', 'Slowest'].map((name) => <th key={name} className="border-b border-rule p-2">{name}</th>)}</tr></thead><tbody>
          {data.analytics.requests.filter((row) => row.status_group === '5xx' || row.max_ms >= 1000).slice(0, 10).map((row) => <tr key={`${row.method}/${row.route}/${row.status_group}`}><td className="p-2 font-mono text-xs">{row.method} {row.route}</td><td className="p-2">{row.status_group}</td><td className="p-2 tabular-nums">{row.count}</td><td className="p-2 tabular-nums">{row.average_ms} ms</td><td className="p-2 tabular-nums">{row.max_ms} ms</td></tr>)}
        </tbody></table></div>
      </section>
      <section aria-labelledby="feed-health" className="space-y-3">
        <h2 id="feed-health" className="text-lg font-semibold">Feed health</h2>
        {!data.feeds.length && <p className="text-sm text-muted">No feed checks recorded yet. They appear after the news pipeline runs.</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          {data.feeds.map((feed) => <article key={`${feed.publisher}/${feed.url}`} className="space-y-1 rounded-xl border border-rule p-4 text-sm">
            <h3 className="font-semibold">{feed.publisher} <span className={feed.ok ? 'text-positive' : 'text-negative'}>· {feed.ok ? 'OK' : 'Failed'}</span></h3>
            <p className="text-muted">{feed.items} items · {feed.full_text_items} with full text · {feed.category}</p>
            <p className="break-all text-xs text-faint">{feed.url}</p>
            <p className="text-xs text-faint">Checked {timestamp(feed.last_checked)}</p>
            {feed.error && <p className="break-words text-negative">{feed.error}</p>}
          </article>)}
        </div>
      </section>
      <section aria-labelledby="background-jobs" className="space-y-3 rounded-2xl border border-rule bg-surface p-5">
        <h2 id="background-jobs" className="text-lg font-semibold">Background jobs</h2>
        <p className="text-sm text-muted">{Object.entries(data.jobs.counts).map(([name, count]) => `${name}: ${count}`).join(' · ') || 'No jobs recorded.'}</p>
        <p className="text-sm text-muted">Web Push: {data.notifications.active} active · {data.notifications.errors} with delivery errors · {data.notifications.total} total</p>
        {!!data.jobs.failed.length && <ul className="divide-y divide-rule rounded-xl border border-rule">{data.jobs.failed.map((job) => <li key={job.id} className="p-3 text-sm"><span className="font-medium">{job.kind}</span> · {job.attempts} attempts · {job.last_error}</li>)}</ul>}
      </section>
      <section aria-labelledby="operational-events" className="space-y-3 rounded-2xl border border-rule bg-surface p-5">
        <h2 id="operational-events" className="text-lg font-semibold">Operational events</h2>
        {!data.events.length ? <p className="text-sm text-muted">No failures or warnings recorded.</p> : <ul className="divide-y divide-rule">
          {data.events.slice(0, 20).map((event, index) => <li key={`${event.created_at}/${event.event}/${index}`} className="py-3 text-sm">
            <p><span className={event.severity === 'info' ? 'text-muted' : 'text-negative'}>{event.severity.toUpperCase()}</span> · <span className="font-medium">{event.component}</span> · {event.event.replaceAll('_', ' ')}</p>
            <p className="text-xs text-faint">{timestamp(event.created_at)}{event.detail ? ` · ${event.detail}` : ''}</p>
          </li>)}
        </ul>}
      </section>
      <section aria-labelledby="pipeline-runs" className="space-y-3">
        <h2 id="pipeline-runs" className="text-lg font-semibold">Recent runs</h2>
        {!data.runs.length ? <p className="text-sm text-muted">No runs recorded yet.</p> : <ul className="divide-y divide-rule rounded-xl border border-rule">
          {data.runs.map((run, i) => <li key={`${run.started_at}/${i}`} className="space-y-1 p-4 text-sm">
            <p className="font-medium">{run.status} · {run.date} · {run.added} added · {run.held_back} held back</p>
            <p className="text-xs text-muted">Started {timestamp(run.started_at)} · finished {timestamp(run.finished_at)}</p>
            {run.error && <p className="break-words text-negative">{run.error}</p>}
          </li>)}
        </ul>}
      </section>
      <section aria-labelledby="held-stories" className="space-y-3">
        <h2 id="held-stories" className="text-lg font-semibold">Stories held back</h2>
        {!data.held_stories?.length ? <p className="text-sm text-muted">No held stories recorded.</p> : <ul className="divide-y divide-rule rounded-xl border border-rule">
          {data.held_stories.map((story, i) => <li key={`${story.created_at}/${i}`} className="space-y-1 p-4 text-sm">
            <p className="font-semibold">{story.headline}</p><p className="text-xs text-muted">{story.date} · {story.category} · {timestamp(story.created_at)}</p>
            <p className="whitespace-pre-wrap break-words text-negative">{story.reason}</p>
          </li>)}
        </ul>}
      </section>
    </div>
  )
}
