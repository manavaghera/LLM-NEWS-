import { Bell, Calculator, Check, Download, ExternalLink, Gauge, History, Mail, Scale, Server, Share2, ShieldQuestion } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import type { ModelSnapshot, NewsItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatShortDate } from '@/lib/format'
import { modelsCsv, monthlyModelCost, parseModelPreferences, selfHostEstimate, type ModelPreferences } from '@/lib/modelTools'
import { api } from '@/api/client'
import { storage } from '@/lib/utils'

const STORE = 'newssense-model-tools-v1'
const money = (value: number) => `$${value < 10 ? value.toFixed(2) : value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const tokenCount = (value: number | null) => value === null ? 'Not listed' : value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2).replace(/\.00$/, '')}M` : `${Math.round(value / 1000)}K`
const isReport = (story: NewsItem) => /^(report|rumou?r|leak|preview)\s*:/i.test(story.headline)

function FeatureTitle({ number, icon, title, note }: { number: number; icon: ReactNode; title: string; note: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-ai-models text-sm font-semibold text-white">{number}</span>
      <div>
        <h2 className="flex items-center gap-2 font-semibold">{icon}{title}</h2>
        <p className="mt-0.5 text-sm text-muted">{note}</p>
      </div>
    </div>
  )
}

function NumberField({ label, value, onChange, min = 0, step = 1 }: { label: string; value: number; onChange: (value: number) => void; min?: number; step?: number }) {
  return (
    <label className="space-y-1 text-xs text-muted">
      <span>{label}</span>
      <input type="number" min={min} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))}
        className="h-10 w-full rounded-lg border border-rule bg-paper px-3 text-sm text-ink" />
    </label>
  )
}

export function ModelWorkbench({ models, updatedAt, stories }: { models: ModelSnapshot[]; updatedAt: string; stories: NewsItem[] }) {
  const [params, setParams] = useSearchParams()
  const [prefs, setPrefs] = useState<ModelPreferences>(() => {
    const saved = parseModelPreferences(storage.get(STORE))
    const shared = (params.get('compare') ?? '').split(',').filter((id) => models.some((model) => model.id === id)).slice(0, 4)
    return shared.length ? { ...saved, selected: shared } : saved
  })
  const [requests, setRequests] = useState(1000)
  const [inputTokens, setInputTokens] = useState(1200)
  const [outputTokens, setOutputTokens] = useState(300)
  const [days, setDays] = useState(30)
  const [requiredMemory, setRequiredMemory] = useState(96)
  const [gpuMemory, setGpuMemory] = useState(24)
  const [gpuPrice, setGpuPrice] = useState(900)

  useEffect(() => storage.set(STORE, JSON.stringify(prefs)), [prefs])

  const selected = prefs.selected.map((id) => models.find((model) => model.id === id)).filter((model): model is ModelSnapshot => !!model)
  const monthly = useMemo(() => models.map((model) => ({ model, cost: monthlyModelCost(model, requests, inputTokens, outputTokens, days) }))
    .sort((a, b) => a.cost - b.cost), [models, requests, inputTokens, outputTokens, days])
  const hosting = selfHostEstimate(requiredMemory, gpuMemory, gpuPrice)
  const reports = stories.filter(isReport)
  const timeline = [...stories].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8)
  const benchmarked = models.filter((model) => prefs.benchmarkScores[model.id] !== undefined)
    .sort((a, b) => (prefs.benchmarkScores[b.id] ?? 0) - (prefs.benchmarkScores[a.id] ?? 0))

  const update = (patch: Partial<ModelPreferences>) => setPrefs((current) => ({ ...current, ...patch }))
  const toggleSelected = (id: string) => {
    if (!prefs.selected.includes(id)) void api.analytics('model_compared', id).catch(() => undefined)
    const next = prefs.selected.includes(id) ? prefs.selected.filter((item) => item !== id) : [...prefs.selected, id].slice(-4)
    update({ selected: next })
    setParams((current) => {
      const copy = new URLSearchParams(current)
      if (next.length) copy.set('compare', next.join(',')); else copy.delete('compare')
      return copy
    }, { replace: true })
  }
  const toggleList = (key: 'watched' | 'digestTopics', value: string) => {
    const list = prefs[key]
    update({ [key]: list.includes(value) ? list.filter((item) => item !== value) : [...list, value] })
  }
  const download = () => {
    const blob = new Blob([modelsCsv(selected.length ? selected : models)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'newssense-model-comparison.csv'; anchor.click(); URL.revokeObjectURL(url)
  }

  return (
    <section id="model-lab" aria-labelledby="model-lab-title" className="scroll-mt-28 space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-ai-models">Model intelligence lab</p>
        <h2 id="model-lab-title" className="headline mt-2 text-4xl font-semibold">Tracking and publishing toolkit</h2>
        <p className="mt-2 text-muted">Ten practical tools for monitoring releases, saving preferences and sharing verified catalog data.</p>
      </div>

      <div className="model-workbench grid gap-6 xl:grid-cols-2">
        <article className="rounded-2xl border border-rule bg-surface p-5 xl:col-span-2">
          <FeatureTitle number={1} icon={<History className="size-4" />} title="Release and change timeline" note={`Catalog snapshot verified ${formatShortDate(updatedAt)}; model stories are labeled confirmed or reported.`} />
          <ol className="mt-5 grid gap-3 md:grid-cols-2">
            <li className="rounded-xl bg-sunken p-4"><p className="text-xs text-muted">{formatShortDate(updatedAt)} · Catalog</p><p className="mt-1 font-medium">Prices and limits checked for {models.length} models</p></li>
            {timeline.map((story) => <li key={`${story.date}-${story.group_id}`} className="rounded-xl bg-sunken p-4">
              <p className="text-xs text-muted">{formatShortDate(story.date)} · {isReport(story) ? 'Reported' : 'Confirmed coverage'}</p>
              <Link to={`/article/${story.date}/${story.group_id}`} className="mt-1 block font-medium hover:text-accent">{story.headline}</Link>
            </li>)}
          </ol>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={2} icon={<Gauge className="size-4" />} title="Your benchmark explorer" note="Enter results from your own eval suite. Scores stay in this browser and are never presented as provider claims." />
          <div className="mt-5 space-y-2">
            {models.map((model) => <label key={model.id} className="flex items-center gap-3 rounded-lg bg-sunken px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate">{model.name}</span>
              <input aria-label={`${model.name} benchmark score`} type="number" min="0" max="100" placeholder="0–100"
                value={prefs.benchmarkScores[model.id] ?? ''}
                onChange={(event) => update({ benchmarkScores: { ...prefs.benchmarkScores, [model.id]: Number(event.target.value) } })}
                className="h-8 w-20 rounded border border-rule bg-paper px-2 text-right" />
            </label>)}
          </div>
          {benchmarked.length > 0 && <p className="mt-3 text-sm text-muted">Current leader: <strong className="text-ink">{benchmarked[0].name}</strong> ({prefs.benchmarkScores[benchmarked[0].id]})</p>}
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={3} icon={<Calculator className="size-4" />} title="Monthly API cost planner" note="Estimate list-price spend from your traffic and token assumptions." />
          <div className="mt-5 grid grid-cols-2 gap-3">
            <NumberField label="Requests per day" value={requests} onChange={setRequests} />
            <NumberField label="Days" value={days} onChange={setDays} min={1} />
            <NumberField label="Input tokens / request" value={inputTokens} onChange={setInputTokens} />
            <NumberField label="Output tokens / request" value={outputTokens} onChange={setOutputTokens} />
          </div>
          <ol className="mt-4 space-y-2 text-sm">{monthly.map(({ model, cost }, index) => <li key={model.id} className="flex justify-between gap-3"><span>{index + 1}. {model.name}</span><strong>{money(cost)}/month</strong></li>)}</ol>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5 xl:col-span-2">
          <FeatureTitle number={4} icon={<Scale className="size-4" />} title="Head-to-head comparison" note="Select up to four models. The comparison is encoded in the URL so you can share it." />
          <div className="mt-5 flex flex-wrap gap-2">{models.map((model) => <button key={model.id} type="button" onClick={() => toggleSelected(model.id)} aria-pressed={prefs.selected.includes(model.id)}
            className={`rounded-full border px-3 py-1.5 text-sm ${prefs.selected.includes(model.id) ? 'border-ai-models bg-sunken' : 'border-rule text-muted'}`}>
            {prefs.selected.includes(model.id) && <Check className="mr-1 inline size-3" />}{model.name}
          </button>)}</div>
          {selected.length > 0 && <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm">
            <thead><tr className="border-b border-rule text-xs text-muted"><th className="py-2">Metric</th>{selected.map((model) => <th key={model.id} className="py-2"><Link to={`/ai-models/${model.id}`} className="hover:text-accent">{model.name}</Link></th>)}</tr></thead>
            <tbody>{[
              ['Provider', ...selected.map((model) => model.provider)],
              ['Input / MTok', ...selected.map((model) => money(model.input_price))],
              ['Output / MTok', ...selected.map((model) => money(model.output_price))],
              ['Context', ...selected.map((model) => tokenCount(model.context_tokens))],
              ['Max output', ...selected.map((model) => tokenCount(model.max_output_tokens))],
              ['Open weights', ...selected.map((model) => model.open_weights ? 'Yes' : 'No')],
            ].map((row) => <tr key={row[0]} className="border-b border-rule last:border-0">{row.map((cell, index) => <td key={index} className={`py-2 pr-4 ${index ? '' : 'font-medium text-muted'}`}>{cell}</td>)}</tr>)}</tbody>
          </table></div>}
          <div className="mt-4 flex flex-wrap gap-2"><Button size="sm" onClick={download}><Download /> Export CSV</Button><Button size="sm" variant="outline" onClick={() => navigator.clipboard?.writeText(window.location.href)}><Share2 /> Copy comparison link</Button></div>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={5} icon={<Bell className="size-4" />} title="Price and model watchlist" note="Set an input-price target. Matching alerts are calculated locally from the newest catalog." />
          <div className="mt-5 space-y-2">{models.map((model) => {
            const watching = prefs.watched.includes(model.id)
            const target = prefs.priceTargets[model.id]
            const matched = watching && typeof target === 'number' && model.input_price <= target
            return <div key={model.id} className="rounded-lg bg-sunken p-3 text-sm">
              <div className="flex items-center gap-2"><button type="button" onClick={() => toggleList('watched', model.id)} className="flex-1 text-left font-medium">{watching ? '★' : '☆'} {model.name}</button>{matched && <span className="text-xs font-semibold text-positive">Target met</span>}</div>
              {watching && <label className="mt-2 flex items-center gap-2 text-xs text-muted">Alert at or below $<input aria-label={`${model.name} input price target`} type="number" min="0" step="0.01" value={target ?? model.input_price}
                onChange={(event) => update({ priceTargets: { ...prefs.priceTargets, [model.id]: Number(event.target.value) } })} className="h-8 w-20 rounded border border-rule bg-paper px-2 text-ink" /> / MTok</label>}
            </div>
          })}</div>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={6} icon={<ShieldQuestion className="size-4" />} title="Rumour tracker" note="Unconfirmed stories stay visibly separated from confirmed model coverage." />
          <div className="mt-5 space-y-3">{reports.length ? reports.map((story) => <Link key={story.group_id} to={`/article/${story.date}/${story.group_id}`} className="block rounded-xl bg-sunken p-3 hover:text-accent"><span className="text-xs text-muted">Reported · {formatShortDate(story.date)}</span><span className="mt-1 block text-sm font-medium">{story.headline}</span></Link>) : <p className="rounded-xl bg-sunken p-4 text-sm text-muted">No unconfirmed model reports in this edition.</p>}</div>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={7} icon={<Server className="size-4" />} title="Self-hosting hardware calculator" note="Use your measured memory requirement; the catalog does not guess model VRAM needs." />
          <div className="mt-5 grid grid-cols-3 gap-3"><NumberField label="Required GB" value={requiredMemory} onChange={setRequiredMemory} /><NumberField label="GB per GPU" value={gpuMemory} onChange={setGpuMemory} min={1} /><NumberField label="Price / GPU" value={gpuPrice} onChange={setGpuPrice} /></div>
          <div className="mt-4 rounded-xl bg-sunken p-4"><p className="text-2xl font-semibold">{hosting.gpuCount} GPUs · {money(hosting.hardwareCost)}</p><p className="mt-1 text-xs text-muted">Hardware purchase estimate only; excludes servers, power, networking and operations.</p></div>
          <p className="mt-3 text-xs text-muted">Open-weight candidates: {models.filter((model) => model.open_weights).map((model) => model.name).join(', ') || 'none listed'}.</p>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={8} icon={<Mail className="size-4" />} title="Topic digest builder" note="Save topics locally and follow the AI Models feed in any RSS or newsletter service." />
          <div className="mt-5 flex flex-wrap gap-2">{['Launches', 'Pricing', 'Open weights', 'Benchmarks', 'Rumours'].map((topic) => <button key={topic} type="button" onClick={() => toggleList('digestTopics', topic)} aria-pressed={prefs.digestTopics.includes(topic)} className={`rounded-full border px-3 py-1.5 text-sm ${prefs.digestTopics.includes(topic) ? 'border-ai-models bg-sunken' : 'border-rule text-muted'}`}>{topic}</button>)}</div>
          <a className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline" href="/feed.xml?category=ai_models" target="_blank" rel="noreferrer">Open the AI Models RSS feed <ExternalLink className="size-3.5" /></a>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={9} icon={<CpuIcon />} title="Company and model pages" note="Every catalog entry now has a stable detail page with specifications and official links." />
          <div className="mt-5 grid gap-2 sm:grid-cols-2">{models.map((model) => <Link key={model.id} to={`/ai-models/${model.id}`} className="rounded-xl bg-sunken p-3 text-sm font-medium hover:text-accent">{model.provider} · {model.name} →</Link>)}</div>
        </article>

        <article className="rounded-2xl border border-rule bg-surface p-5">
          <FeatureTitle number={10} icon={<ExternalLink className="size-4" />} title="Public API and widget" note="Use the source-linked catalog in another app or embed the compact comparison table." />
          <div className="mt-5 space-y-3 text-sm">
            <a href="/models/catalog.json" target="_blank" rel="noreferrer" className="block rounded-xl bg-sunken p-3 font-mono text-xs hover:text-accent">GET /models/catalog.json</a>
            <a href="/widgets/models" target="_blank" rel="noreferrer" className="block rounded-xl bg-sunken p-3 font-mono text-xs hover:text-accent">EMBED /widgets/models</a>
            <code className="block overflow-x-auto rounded-xl border border-rule p-3 text-xs">{'<iframe src="https://your-domain/widgets/models" title="AI model prices"></iframe>'}</code>
          </div>
        </article>
      </div>
    </section>
  )
}

function CpuIcon() {
  return <span aria-hidden className="text-sm">◫</span>
}
