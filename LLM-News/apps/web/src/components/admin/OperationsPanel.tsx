import { useState } from 'react'
import { api } from '@/api/client'
import type { Operations, PipelineUsage } from '@/api/types'
import { Button } from '@/components/ui/button'

const timestamp = (value?: string | null) => value ? new Date(value).toLocaleString() : 'Not recorded'

export function OperationsPanel({ data, token, onBudget }: { data: Operations; token: string; onBudget: (usage: PipelineUsage) => void }) {
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
        <h2 id="pipeline-health" className="mb-3 text-lg font-semibold">Pipeline health</h2>
        <dl className="grid gap-4 text-sm sm:grid-cols-3">
          <div><dt className="text-muted">Latest update</dt><dd>{timestamp(data.update.last_update)}</dd></div>
          <div><dt className="text-muted">Next update</dt><dd>{timestamp(data.update.next_update)}</dd></div>
          <div><dt className="text-muted">Latest update status</dt><dd className={data.update.ok === null ? 'text-muted' : data.update.ok ? 'text-positive' : 'text-negative'}>{data.update.ok === null ? 'Not recorded' : data.update.ok ? 'Healthy' : 'Needs attention'} · {data.update.added} added</dd></div>
        </dl>
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
        {!!data.jobs.failed.length && <ul className="divide-y divide-rule rounded-xl border border-rule">{data.jobs.failed.map((job) => <li key={job.id} className="p-3 text-sm"><span className="font-medium">{job.kind}</span> · {job.attempts} attempts · {job.last_error}</li>)}</ul>}
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
