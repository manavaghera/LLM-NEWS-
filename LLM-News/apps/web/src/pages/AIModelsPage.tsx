import { ArrowDown, Cpu, ExternalLink, Radio, ShieldQuestion, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useModelCatalog, useNews } from '@/api/queries'
import type { ModelSnapshot, NewsItem } from '@/api/types'
import { StoryCard } from '@/components/news/StoryCard'
import { ModelWorkbench } from '@/components/models/ModelWorkbench'
import { ModelDecisionStudio } from '@/components/models/ModelDecisionStudio'
import { ChartCard } from '@/components/trends/chartKit'
import { axisProps, useChartColors } from '@/components/trends/chartKit'
import { EmptyState, ErrorState } from '@/components/ui/feedback'
import { Reveal } from '@/components/ui/Reveal'
import { useEdition } from '@/hooks/useEdition'
import { formatLongDate, plural } from '@/lib/format'

const reported = (story: NewsItem) => /^(report|rumou?r|leak|preview)\s*:/i.test(story.headline)
const money = (value: number) => `$${value < 1 ? value.toFixed(2) : value.toFixed(2).replace(/\.00$/, '')}`
const tokens = (value: number | null) => value === null ? 'Not listed' : value >= 1_000_000
  ? `${(value / 1_000_000).toFixed(value % 1_000_000 ? 2 : 0)}M`
  : `${Math.round(value / 1_000)}K`

const WORKLOADS = [
  { id: 'chat', label: 'Chat app', description: '1M input + 250K output tokens', input: 1, output: 0.25 },
  { id: 'agent', label: 'Coding agent', description: '5M input + 1M output tokens', input: 5, output: 1 },
  { id: 'documents', label: 'Document analysis', description: '10M input + 500K output tokens', input: 10, output: 0.5 },
] as const

type ModelRow = ModelSnapshot & {
  short_name: string
  workload_cost: number
  context_m: number
  context_k: number
  output_k: number
  frontier: boolean
}

function WorkloadTooltip({ active, payload }: { active?: boolean; payload?: { payload?: ModelRow }[] }) {
  const model = payload?.[0]?.payload
  if (!active || !model) return null
  return (
    <div className="min-w-52 rounded-xl border border-rule bg-surface px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold">{model.name}</p>
      <p className="mt-1 flex justify-between gap-5"><span className="text-muted">Estimated cost</span><strong>{money(model.workload_cost)}</strong></p>
      <p className="flex justify-between gap-5"><span className="text-muted">Context</span><strong>{tokens(model.context_tokens)}</strong></p>
      <p className="flex justify-between gap-5"><span className="text-muted">Input / output</span><strong>{money(model.input_price)} / {money(model.output_price)}</strong></p>
      {model.frontier && <p className="mt-1 text-xs font-medium text-ai-models">Cost–context frontier</p>}
    </div>
  )
}

function NewsGrid({ items }: { items: NewsItem[] }) {
  return (
    <div className="grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => <StoryCard key={item.group_id} item={item} showCategory={false} />)}
    </div>
  )
}

function FitGuide({ models }: { models: ModelSnapshot[] }) {
  return (
    <section id="directory" aria-labelledby="fit-guide" className="scroll-mt-28 space-y-4">
      <div>
        <h2 id="fit-guide" className="headline text-3xl font-semibold">Best fit by use case</h2>
        <p className="mt-1 text-sm text-muted">A practical shortlist from provider positioning, price, context and deployment options—not a quality leaderboard.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {models.map((model) => (
          <article key={model.id} className="rounded-2xl border border-rule bg-surface p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ai-models">{model.provider}</p>
                <h3 className="mt-1 text-lg font-semibold"><Link to={`/ai-models/${model.id}`} className="hover:text-accent">{model.name}</Link></h3>
              </div>
              {model.open_weights && <span className="rounded-full bg-sunken px-2.5 py-1 text-xs text-muted">Open weights</span>}
            </div>
            <ul className="mt-4 flex flex-wrap gap-2">
              {model.best_for.map((use) => <li key={use} className="rounded-full bg-sunken px-3 py-1 text-xs">{use}</li>)}
            </ul>
            <p className="mt-4 text-sm leading-relaxed text-muted">{model.notes}</p>
            <a href={model.source_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline">
              Official model details <ExternalLink className="size-3.5" />
            </a>
          </article>
        ))}
      </div>
    </section>
  )
}

function ModelCharts({ models }: { models: ModelSnapshot[] }) {
  const colors = useChartColors()
  const [workloadId, setWorkloadId] = useState<(typeof WORKLOADS)[number]['id']>('chat')
  const [availability, setAvailability] = useState<'all' | 'open' | 'hosted'>('all')
  const workload = WORKLOADS.find((item) => item.id === workloadId) ?? WORKLOADS[0]
  const available = models.filter((model) => availability === 'all' || model.open_weights === (availability === 'open'))
  const baseRows = available.map((model) => ({
    ...model,
    short_name: model.name.replace(/^Claude /, '').replace(/^Gemini /, ''),
    workload_cost: Number((model.input_price * workload.input + model.output_price * workload.output).toFixed(3)),
    context_m: Number((model.context_tokens / 1_000_000).toFixed(3)),
    context_k: Math.round(model.context_tokens / 1000),
    output_k: Math.round((model.max_output_tokens ?? 0) / 1000),
  }))
  const rows: ModelRow[] = baseRows.map((model) => ({
    ...model,
    frontier: !baseRows.some((other) => other.id !== model.id
      && other.workload_cost <= model.workload_cost
      && other.context_tokens >= model.context_tokens
      && (other.workload_cost < model.workload_cost || other.context_tokens > model.context_tokens)),
  }))
  const byCost = [...rows].sort((a, b) => a.workload_cost - b.workload_cost)
  const cheapest = byCost[0]
  const largestContext = [...rows].sort((a, b) => b.context_tokens - a.context_tokens)[0]
  const filters = [
    { value: 'all', label: 'All models' },
    { value: 'open', label: 'Open weights' },
    { value: 'hosted', label: 'Hosted only' },
  ] as const

  return (
    <section id="compare" aria-labelledby="compare-models" className="scroll-mt-28 space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="compare-models" className="headline text-3xl font-semibold">Compare models</h2>
          <p className="mt-1 text-sm text-muted">Choose a deployment type and a realistic token workload. Lower cost and larger limits are better; quality is intentionally not guessed.</p>
        </div>
        <div className="flex rounded-full bg-sunken p-1" role="group" aria-label="Filter model availability">
          {filters.map((filter) => (
            <button key={filter.value} type="button" onClick={() => setAvailability(filter.value)} aria-pressed={availability === filter.value}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${availability === filter.value ? 'bg-ink text-paper' : 'text-muted hover:text-ink'}`}>
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {cheapest && largestContext && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl bg-sunken p-4"><p className="text-xs uppercase tracking-wide text-muted">Lowest estimated cost</p><p className="mt-1 font-semibold">{cheapest.name} · {money(cheapest.workload_cost)}</p></div>
          <div className="rounded-2xl bg-sunken p-4"><p className="text-xs uppercase tracking-wide text-muted">Largest context</p><p className="mt-1 font-semibold">{largestContext.name} · {tokens(largestContext.context_tokens)}</p></div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard
          title="Estimated workload cost"
          subtitle={`${workload.description}. Uses standard list price; cache, batch and regional discounts are excluded.`}
          table={{
            columns: ['Model', 'Estimated cost', 'Input / MTok', 'Output / MTok'],
            rows: byCost.map((m) => [m.name, money(m.workload_cost), money(m.input_price), money(m.output_price)]),
          }}
          className="xl:col-span-2"
        >
          <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Choose workload">
            {WORKLOADS.map((option) => (
              <button key={option.id} type="button" onClick={() => setWorkloadId(option.id)} aria-pressed={workloadId === option.id}
                className={`rounded-xl border px-3 py-2 text-left text-xs transition-colors ${workloadId === option.id ? 'border-ai-models bg-sunken text-ink' : 'border-rule text-muted hover:text-ink'}`}>
                <span className="block font-semibold">{option.label}</span><span>{option.description}</span>
              </button>
            ))}
          </div>
          <div className="h-72" role="img" aria-label={`Bar chart comparing model cost for ${workload.label}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byCost} layout="vertical" margin={{ top: 0, right: 54, bottom: 18, left: 8 }}>
                <CartesianGrid stroke={colors.rule} horizontal={false} />
                <XAxis type="number" {...axisProps(colors)} tickFormatter={(value) => `$${value}`} label={{ value: 'Estimated USD', position: 'insideBottom', offset: -8, fill: colors.muted }} />
                <YAxis type="category" dataKey="short_name" width={122} {...axisProps(colors)} tick={{ fill: colors.ink, fontSize: 12 }} />
                <Tooltip content={<WorkloadTooltip />} cursor={{ fill: colors.sunken }} />
                <Bar dataKey="workload_cost" name="Estimated cost" radius={[0, 5, 5, 0]}>
                  {byCost.map((model, index) => <Cell key={model.id} fill={index === 0 ? colors['series-ai_models'] : colors['series-tech']} fillOpacity={index === 0 ? 1 : 0.72} />)}
                  <LabelList dataKey="workload_cost" position="right" fill={colors.ink} fontSize={11} formatter={(value: unknown) => money(Number(value))} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          title="Context and output limits"
          subtitle="Maximum accepted context and, where the provider publishes it, maximum generated output"
          table={{
            columns: ['Model', 'Context', 'Maximum output'],
            rows: rows.map((m) => [m.name, tokens(m.context_tokens), tokens(m.max_output_tokens)]),
          }}
        >
          <div className="h-80" role="img" aria-label="Bar chart comparing context and maximum output token limits">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 8, bottom: 18, left: 8 }}>
                <CartesianGrid stroke={colors.rule} horizontal={false} />
                <XAxis type="number" {...axisProps(colors)} tickFormatter={(value) => `${value}K`} label={{ value: 'Thousands of tokens', position: 'insideBottom', offset: -8, fill: colors.muted }} />
                <YAxis type="category" dataKey="short_name" width={112} {...axisProps(colors)} tick={{ fill: colors.ink, fontSize: 12 }} />
                <Tooltip formatter={(value, name) => [`${Number(value).toLocaleString()}K`, name]} contentStyle={{ background: colors.surface, borderColor: colors.rule, borderRadius: 12 }} />
                <Bar dataKey="context_k" name="Context" fill={colors['series-ai_models']} radius={[0, 4, 4, 0]} />
                <Bar dataKey="output_k" name="Max output" fill={colors['series-tech']} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard
          title="Cost–context map"
          subtitle="Highlighted models offer more context, lower cost, or both. This is not a quality ranking."
          table={{
            columns: ['Model', 'Estimated cost', 'Context', 'Frontier'],
            rows: rows.map((m) => [m.name, money(m.workload_cost), tokens(m.context_tokens), m.frontier ? 'Yes' : 'No']),
          }}
        >
          <div className="h-80" role="img" aria-label="Scatter chart comparing estimated workload cost with context window size">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 28, right: 24, bottom: 20, left: 0 }}>
                <CartesianGrid stroke={colors.rule} />
                <XAxis type="number" dataKey="workload_cost" name="Estimated cost" {...axisProps(colors)} tickFormatter={(value) => `$${value}`} label={{ value: 'Estimated USD', position: 'insideBottom', offset: -10, fill: colors.muted }} />
                <YAxis type="number" dataKey="context_m" name="Context" unit="M" width={46} {...axisProps(colors)} />
                <Tooltip content={<WorkloadTooltip />} cursor={{ stroke: colors.faint, strokeDasharray: '3 3' }} />
                <Scatter data={rows}>
                  {rows.map((model) => <Cell key={model.id} fill={model.frontier ? colors['series-ai_models'] : colors.faint} />)}
                  <LabelList dataKey="short_name" position="top" fill={colors.ink} fontSize={11} />
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>
    </section>
  )
}

export function AIModelsPage() {
  const edition = useEdition()
  const news = useNews(edition.date)
  const catalog = useModelCatalog()
  const modelNews = useMemo(() => (news.data ?? []).filter((item) => item.category === 'ai_models'), [news.data])
  const reports = modelNews.filter(reported)
  const confirmed = modelNews.filter((item) => !reported(item))

  return (
    <div className="space-y-20 pb-8">
      <title>AI model news, prices and comparison tools · NewsSense</title>
      <meta name="description" content="Track AI model launches and rumours, compare verified list prices and context limits, and plan model choices with private interactive tools." />
      <link rel="canonical" href={`${window.location.origin}/ai-models`} />
      <header className="model-hero-grid relative isolate overflow-hidden rounded-[2rem] border border-rule bg-surface px-6 py-10 sm:px-10 sm:py-14 lg:px-14 lg:py-16">
        <div aria-hidden className="absolute -right-20 -top-20 -z-10 size-72 rounded-full bg-ai-models/10 blur-3xl" />
        <div className="grid items-end gap-10 lg:grid-cols-[1fr_18rem]">
          <div className="max-w-3xl">
            <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.17em] text-ai-models"><Sparkles className="size-4" /> AI model intelligence</p>
            <h1 className="headline mt-5 text-5xl font-semibold leading-[0.94] tracking-tight sm:text-7xl">Choose your next model with evidence.</h1>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">Explore verified prices, context limits, model news and private planning tools in one focused workspace.</p>
            <div className="mt-8 flex flex-wrap gap-3"><a href="#decision-studio" className="inline-flex h-11 items-center gap-2 rounded-full bg-ink px-5 text-sm font-medium text-paper">Open decision studio <ArrowDown className="size-4" /></a><a href="#compare" className="inline-flex h-11 items-center rounded-full border border-rule bg-surface px-5 text-sm font-medium">Compare models</a></div>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
            <div className="rounded-2xl border border-rule bg-paper/80 p-5 backdrop-blur"><p className="text-3xl font-semibold">{catalog.data?.models.length ?? '—'}</p><p className="mt-1 text-xs uppercase tracking-wide text-muted">source-linked models</p></div>
            <div className="rounded-2xl border border-rule bg-paper/80 p-5 backdrop-blur"><p className="text-3xl font-semibold">23</p><p className="mt-1 text-xs uppercase tracking-wide text-muted">interactive tools</p></div>
            <div className="col-span-2 rounded-2xl border border-rule bg-paper/80 p-5 backdrop-blur lg:col-span-1"><p className="text-sm font-medium">Live edition pulse</p><p className="mt-1 text-xs text-muted">{modelNews.length} model {modelNews.length === 1 ? 'story' : 'stories'} · {reports.length} reported</p></div>
          </div>
        </div>
      </header>

      <nav id="model-page-nav" aria-label="AI Models sections" className="z-20 -mx-1 flex gap-1 overflow-x-auto rounded-2xl border border-rule bg-paper/90 p-1.5 shadow-sm backdrop-blur [scrollbar-width:none] lg:sticky lg:top-20">
        {[['Compare', '#compare'], ['Decision studio', '#decision-studio'], ['Tracking tools', '#model-lab'], ['Directory', '#directory'], ['Model news', '#model-news']].map(([label, href]) => <a key={href} href={href} className="whitespace-nowrap rounded-xl px-4 py-2 text-sm text-muted transition-colors hover:bg-sunken hover:text-ink">{label}</a>)}
      </nav>

      {catalog.error ? (
        <ErrorState title="Couldn't load the model comparison" error={catalog.error} onRetry={() => catalog.refetch()} />
      ) : catalog.data ? (
        <>
          <Reveal><ModelCharts models={catalog.data.models} /></Reveal>
          <ModelDecisionStudio models={catalog.data.models} updatedAt={catalog.data.updated_at} />
          <Reveal><ModelWorkbench models={catalog.data.models} updatedAt={catalog.data.updated_at} stories={modelNews} /></Reveal>
          <Reveal><FitGuide models={catalog.data.models} /></Reveal>
          <Reveal><p className="rounded-xl border border-rule px-4 py-3 text-xs leading-relaxed text-muted">
            Pricing snapshot verified {formatLongDate(catalog.data.updated_at)}. {catalog.data.methodology} Prices can change; each card links to the provider source.
          </p></Reveal>
        </>
      ) : (
        <div className="shimmer h-96 rounded-2xl" aria-label="Loading model comparison" />
      )}

      <Reveal><section id="model-news" aria-labelledby="model-news-title" className="scroll-mt-28 space-y-7">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-rule pb-4">
          <div>
            <h2 id="model-news-title" className="headline text-3xl font-semibold">Model news</h2>
            <p className="mt-1 text-sm text-muted">{edition.date ? `${formatLongDate(edition.date)} · ${plural(modelNews.length, 'story')}` : 'Latest edition'}</p>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="inline-flex items-center gap-1 rounded-full bg-sunken px-3 py-1.5"><Radio className="size-3.5" /> {confirmed.length} confirmed coverage</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-sunken px-3 py-1.5"><ShieldQuestion className="size-3.5" /> {reports.length} reported / preview</span>
          </div>
        </div>
        {edition.error || news.error ? (
          <ErrorState title="Couldn't load AI model news" error={edition.error ?? news.error} onRetry={() => { edition.refetch(); void news.refetch() }} />
        ) : modelNews.length ? (
          <NewsGrid items={[...reports, ...confirmed]} />
        ) : (
          <EmptyState icon={<Cpu />} title="No AI model stories in this edition">
            <p>The hourly updater will add model launches and well-sourced reports when the feeds contain them.</p>
          </EmptyState>
        )}
      </section></Reveal>
    </div>
  )
}
