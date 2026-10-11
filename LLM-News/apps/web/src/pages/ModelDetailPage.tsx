import { ArrowLeft, ExternalLink } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { useModelCatalog } from '@/api/queries'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'

const money = (value: number) => `$${value.toFixed(2).replace(/\.00$/, '')}`
const tokens = (value: number | null) => value === null ? 'Not listed' : value >= 1_000_000
  ? `${(value / 1_000_000).toFixed(2).replace(/\.00$/, '')}M`
  : `${Math.round(value / 1_000)}K`

export function ModelDetailPage() {
  const { modelId } = useParams()
  const catalog = useModelCatalog()

  if (catalog.error) return <ErrorState title="Couldn't load this model" error={catalog.error} onRetry={() => catalog.refetch()} />
  if (!catalog.data) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-80" /></div>

  const model = catalog.data.models.find((item) => item.id === modelId)
  if (!model) return <EmptyState icon={<span>404</span>} title="Model not found"><Link className="text-accent hover:underline" to="/ai-models">Return to AI Models</Link></EmptyState>

  const facts = [
    ['Input price / MTok', money(model.input_price)],
    ['Output price / MTok', money(model.output_price)],
    ['Context window', tokens(model.context_tokens)],
    ['Maximum output', tokens(model.max_output_tokens)],
    ['Multimodal', model.multimodal ? 'Yes' : 'No'],
    ['Open weights', model.open_weights ? 'Yes' : 'No'],
  ]

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <title>{`${model.name} price, context and details · NewsSense`}</title>
      <meta name="description" content={`${model.provider} ${model.name}: pricing, context window, capabilities, use cases and official sources.`} />
      <link rel="canonical" href={`${window.location.origin}/ai-models/${model.id}`} />
      <Link to="/ai-models" className="inline-flex items-center gap-2 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> AI Models</Link>
      <header className="rounded-3xl bg-sunken p-7 sm:p-10">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-ai-models">{model.provider} · {model.status}</p>
        <h1 className="headline mt-3 text-4xl font-semibold sm:text-6xl">{model.name}</h1>
        <p className="mt-4 max-w-3xl text-lg leading-relaxed text-muted">{model.notes}</p>
      </header>

      <section aria-labelledby="model-specifications">
        <h2 id="model-specifications" className="headline text-3xl font-semibold">Specifications and list price</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {facts.map(([label, value]) => <div key={label} className="rounded-2xl border border-rule bg-surface p-5"><p className="text-xs uppercase tracking-wide text-muted">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-2xl border border-rule bg-surface p-6">
          <h2 className="text-lg font-semibold">Best suited for</h2>
          <ul className="mt-4 flex flex-wrap gap-2">{model.best_for.map((use) => <li key={use} className="rounded-full bg-sunken px-3 py-1.5 text-sm">{use}</li>)}</ul>
        </div>
        <div className="rounded-2xl border border-rule bg-surface p-6">
          <h2 className="text-lg font-semibold">Official sources</h2>
          <div className="mt-4 space-y-3 text-sm">
            <a href={model.source_url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-xl bg-sunken p-3 hover:text-accent">Model details <ExternalLink className="size-4" /></a>
            <a href={model.pricing_url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-xl bg-sunken p-3 hover:text-accent">Current pricing <ExternalLink className="size-4" /></a>
          </div>
        </div>
      </section>

      <p className="text-xs text-muted">Catalog snapshot: {catalog.data.updated_at}. {catalog.data.methodology}</p>
    </div>
  )
}
