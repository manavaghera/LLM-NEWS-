import { Activity, BadgeDollarSign, BookOpenCheck, BriefcaseBusiness, Check, Clipboard, Compass, Database, FileText, Filter, Gauge, LineChart, Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ModelSnapshot } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Reveal } from '@/components/ui/Reveal'
import { storage } from '@/lib/utils'

const STORE = 'newssense-decision-studio-v1'
const money = (value: number) => `$${value < 10 ? value.toFixed(2) : value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const tokens = (value: number | null) => value === null ? '—' : value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2).replace(/\.00$/, '')}M` : `${Math.round(value / 1000)}K`
const clamp = (value: number) => Number.isFinite(value) ? Math.max(0, value) : 0

function ToolHeading({ number, icon, title, note }: { number: number; icon: ReactNode; title: string; note: string }) {
  return <div><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-ai-models"><span>{number}</span>{icon}<span>{title}</span></div><p className="mt-2 text-sm leading-relaxed text-muted">{note}</p></div>
}

function Range({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label className="block text-xs text-muted"><span className="flex justify-between"><span>{label}</span><strong className="text-ink">{value}%</strong></span><input className="mt-2 w-full accent-[var(--ai-models)]" type="range" min="0" max="100" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>
}

function Numeric({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (value: number) => void; step?: number }) {
  return <label className="block text-xs text-muted"><span>{label}</span><input className="mt-1 h-10 w-full rounded-xl border border-rule bg-paper px-3 text-sm text-ink" type="number" min="0" step={step} value={value} onChange={(event) => onChange(clamp(Number(event.target.value)))} /></label>
}

export function ModelDecisionStudio({ models, updatedAt }: { models: ModelSnapshot[]; updatedAt: string }) {
  const [query, setQuery] = useState('')
  const [onlyOpen, setOnlyOpen] = useState(false)
  const [onlyMultimodal, setOnlyMultimodal] = useState(false)
  const uses = useMemo(() => [...new Set(models.flatMap((model) => model.best_for))], [models])
  const [useCase, setUseCase] = useState(uses[0] ?? '')
  const [monthlyInput, setMonthlyInput] = useState(30)
  const [monthlyOutput, setMonthlyOutput] = useState(5)
  const [budget, setBudget] = useState(100)
  const [documentTokens, setDocumentTokens] = useState(200_000)
  const [currentId, setCurrentId] = useState(models[0]?.id ?? '')
  const [targetId, setTargetId] = useState(models[1]?.id ?? models[0]?.id ?? '')
  const [costWeight, setCostWeight] = useState(55)
  const [contextWeight, setContextWeight] = useState(45)
  const [priceShock, setPriceShock] = useState(20)
  const [annualGrowth, setAnnualGrowth] = useState(8)
  const [noteModel, setNoteModel] = useState(models[0]?.id ?? '')
  const [copied, setCopied] = useState(false)
  const [notes, setNotes] = useState<Record<string, string>>(() => {
    try { return JSON.parse(storage.get(STORE) ?? '{}') as Record<string, string> } catch { return {} }
  })

  useEffect(() => storage.set(STORE, JSON.stringify(notes)), [notes])

  const monthlyCost = (model: ModelSnapshot, multiplier = 1) => (model.input_price * monthlyInput + model.output_price * monthlyOutput) * multiplier
  const costs = models.map((model) => monthlyCost(model))
  const minCost = Math.min(...costs)
  const maxCost = Math.max(...costs)
  const maxContext = Math.max(...models.map((model) => model.context_tokens))
  const scored = models.map((model) => {
    const costScore = maxCost === minCost ? 1 : 1 - ((monthlyCost(model) - minCost) / (maxCost - minCost))
    const contextScore = model.context_tokens / maxContext
    const total = ((costScore * costWeight) + (contextScore * contextWeight)) / Math.max(1, costWeight + contextWeight)
    return { model, total: Math.round(total * 100) }
  }).sort((a, b) => b.total - a.total)
  const filtered = models.filter((model) => {
    const haystack = `${model.name} ${model.provider} ${model.best_for.join(' ')}`.toLowerCase()
    return haystack.includes(query.toLowerCase()) && (!onlyOpen || model.open_weights) && (!onlyMultimodal || model.multimodal)
  })
  const useMatches = [...models].sort((a, b) => Number(b.best_for.includes(useCase)) - Number(a.best_for.includes(useCase)) || monthlyCost(a) - monthlyCost(b))
  const budgetFits = models.filter((model) => monthlyCost(model) <= budget).sort((a, b) => monthlyCost(a) - monthlyCost(b))
  const contextFits = models.filter((model) => model.context_tokens >= documentTokens).sort((a, b) => a.context_tokens - b.context_tokens)
  const current = models.find((model) => model.id === currentId) ?? models[0]
  const target = models.find((model) => model.id === targetId) ?? models[0]
  const monthlySavings = current && target ? monthlyCost(current) - monthlyCost(target) : 0
  const shockRows = [...models].map((model) => ({ model, cost: monthlyCost(model, 1 + priceShock / 100) })).sort((a, b) => a.cost - b.cost)
  const annual = target ? Array.from({ length: 12 }, (_, index) => monthlyCost(target) * ((1 + annualGrowth / 100) ** index)).reduce((sum, value) => sum + value, 0) : 0
  const frontier = models.filter((model) => !models.some((other) => other.id !== model.id && monthlyCost(other) <= monthlyCost(model) && other.context_tokens >= model.context_tokens && (monthlyCost(other) < monthlyCost(model) || other.context_tokens > model.context_tokens)))
  const brief = target ? `${target.name} is the current choice for a ${monthlyInput}M input / ${monthlyOutput}M output monthly workload. Estimated list-price spend: ${money(monthlyCost(target))}/month and ${money(annual)}/year at ${annualGrowth}% monthly workload growth. It fits a ${tokens(documentTokens)} context requirement. Weighted fit score: ${scored.find((row) => row.model.id === target.id)?.total ?? 0}/100 (${costWeight}% cost, ${contextWeight}% context). Verify against official pricing before production use.` : ''

  const copyBrief = async () => {
    await navigator.clipboard?.writeText(brief)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  const selectClass = 'mt-3 h-10 w-full rounded-xl border border-rule bg-paper px-3 text-sm text-ink'
  const cardClass = 'model-studio-card rounded-3xl border border-rule bg-surface p-5 sm:p-6'

  return <section id="decision-studio" aria-labelledby="decision-title" className="scroll-mt-28 space-y-7">
    <Reveal><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[0.15em] text-ai-models">Decision studio</p><h2 id="decision-title" className="headline mt-2 text-4xl font-semibold sm:text-5xl">Thirteen new ways to find your fit</h2><p className="mt-3 max-w-2xl text-muted">A private planning workspace built from published prices and limits. Your notes stay in this browser.</p></div><span className="rounded-full border border-rule bg-surface px-4 py-2 text-xs text-muted">Catalog checked {updatedAt}</span></div></Reveal>

    <div className="grid gap-5 lg:grid-cols-12">
      <Reveal className="lg:col-span-8"><article className={cardClass}><ToolHeading number={11} icon={<Search className="size-4" />} title="Smart model finder" note="Search providers, model names and published best-fit labels, then narrow by deployment capability." /><div className="mt-5 flex flex-col gap-3 sm:flex-row"><label className="relative flex-1"><Search className="absolute left-3 top-3 size-4 text-faint" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models or use cases" className="h-10 w-full rounded-xl border border-rule bg-paper pl-10 pr-3 text-sm" /></label><button type="button" onClick={() => setOnlyOpen((value) => !value)} aria-pressed={onlyOpen} className={`rounded-xl border px-3 text-sm ${onlyOpen ? 'border-ai-models bg-sunken' : 'border-rule text-muted'}`}><Filter className="mr-1 inline size-3" /> Open weights</button><button type="button" onClick={() => setOnlyMultimodal((value) => !value)} aria-pressed={onlyMultimodal} className={`rounded-xl border px-3 text-sm ${onlyMultimodal ? 'border-ai-models bg-sunken' : 'border-rule text-muted'}`}>Multimodal</button></div><div className="mt-4 grid gap-2 sm:grid-cols-2">{filtered.map((model) => <div key={model.id} className="flex items-center justify-between rounded-2xl bg-sunken p-3 text-sm"><span><strong>{model.name}</strong><span className="block text-xs text-muted">{model.provider}</span></span><span className="text-xs text-muted">{money(monthlyCost(model))}/mo</span></div>)}{!filtered.length && <p className="text-sm text-muted">No models match these filters.</p>}</div></article></Reveal>

      <Reveal className="lg:col-span-4" delay={80}><article className={cardClass}><ToolHeading number={12} icon={<Compass className="size-4" />} title="Use-case matcher" note="Ranks exact catalog labels first, then sorts matching choices by your workload cost." /><select className={selectClass} value={useCase} onChange={(event) => setUseCase(event.target.value)}>{uses.map((use) => <option key={use}>{use}</option>)}</select><div className="mt-4 space-y-2">{useMatches.slice(0, 3).map((model, index) => <div key={model.id} className="flex items-center gap-3 rounded-xl bg-sunken p-3"><span className="text-lg font-semibold text-faint">0{index + 1}</span><div className="min-w-0"><p className="truncate text-sm font-medium">{model.name}</p><p className="text-xs text-muted">{model.best_for.includes(useCase) ? 'Direct match' : 'Alternative'} · {money(monthlyCost(model))}/mo</p></div></div>)}</div></article></Reveal>

      <Reveal className="lg:col-span-4"><article className={cardClass}><ToolHeading number={13} icon={<BadgeDollarSign className="size-4" />} title="Budget guardrail" note="Set a ceiling for the shared monthly workload." /><div className="mt-5 grid grid-cols-3 gap-2"><Numeric label="Input MTok" value={monthlyInput} onChange={setMonthlyInput} step={0.5} /><Numeric label="Output MTok" value={monthlyOutput} onChange={setMonthlyOutput} step={0.5} /><Numeric label="Budget USD" value={budget} onChange={setBudget} /></div><p className="mt-4 text-3xl font-semibold">{budgetFits.length}<span className="ml-2 text-sm font-normal text-muted">models under budget</span></p><p className="mt-2 text-xs text-muted">{budgetFits.map((model) => model.name).join(' · ') || 'Increase the budget or reduce usage.'}</p></article></Reveal>

      <Reveal className="lg:col-span-4" delay={60}><article className={cardClass}><ToolHeading number={14} icon={<BookOpenCheck className="size-4" />} title="Context-fit checker" note="Check whether a document or conversation fits the published context window." /><div className="mt-5"><Numeric label="Required tokens" value={documentTokens} onChange={setDocumentTokens} step={1000} /></div><div className="mt-4 space-y-2">{models.map((model) => <div key={model.id} className="flex justify-between text-sm"><span>{model.name}</span><span className={model.context_tokens >= documentTokens ? 'text-positive' : 'text-negative'}>{model.context_tokens >= documentTokens ? 'Fits' : 'Too small'}</span></div>)}</div><p className="mt-3 text-xs text-muted">Smallest fit: {contextFits[0]?.name ?? 'none'}.</p></article></Reveal>

      <Reveal className="lg:col-span-4" delay={120}><article className={cardClass}><ToolHeading number={15} icon={<BriefcaseBusiness className="size-4" />} title="Migration savings" note="Compare the same workload across a current and proposed model." /><select className={selectClass} value={currentId} onChange={(event) => setCurrentId(event.target.value)}>{models.map((model) => <option key={model.id} value={model.id}>From {model.name}</option>)}</select><select className={selectClass} value={targetId} onChange={(event) => setTargetId(event.target.value)}>{models.map((model) => <option key={model.id} value={model.id}>To {model.name}</option>)}</select><p className={`mt-4 text-3xl font-semibold ${monthlySavings >= 0 ? 'text-positive' : 'text-negative'}`}>{monthlySavings >= 0 ? 'Save ' : 'Add '}{money(Math.abs(monthlySavings))}<span className="text-sm font-normal text-muted"> / month</span></p></article></Reveal>

      <Reveal className="lg:col-span-7"><article className={cardClass}><ToolHeading number={16} icon={<SlidersHorizontal className="size-4" />} title="Weighted fit score" note="Choose how much factual price and context capacity matter. This is a preference score, not a quality benchmark." /><div className="mt-5 grid gap-4 sm:grid-cols-2"><Range label="Lower cost" value={costWeight} onChange={setCostWeight} /><Range label="Larger context" value={contextWeight} onChange={setContextWeight} /></div><div className="mt-5 space-y-3">{scored.map(({ model, total }, index) => <div key={model.id} className="grid grid-cols-[1fr_auto] items-center gap-3"><div><div className="flex justify-between text-xs"><span>{index + 1}. {model.name}</span><span>{total}/100</span></div><div className="mt-1 h-1.5 overflow-hidden rounded-full bg-sunken"><div className="h-full rounded-full bg-ai-models transition-[width] duration-500" style={{ width: `${total}%` }} /></div></div></div>)}</div></article></Reveal>

      <Reveal className="lg:col-span-5" delay={80}><article className={cardClass}><ToolHeading number={17} icon={<Activity className="size-4" />} title="Price-shock simulator" note="Stress test the workload against a uniform list-price increase." /><Range label="Price increase" value={priceShock} onChange={setPriceShock} /><div className="mt-5 space-y-2">{shockRows.map(({ model, cost }) => <div key={model.id} className="flex justify-between text-sm"><span>{model.name}</span><strong>{money(cost)}</strong></div>)}</div></article></Reveal>

      <Reveal className="lg:col-span-4"><article className={cardClass}><ToolHeading number={18} icon={<LineChart className="size-4" />} title="Annual spend projection" note="Projects the selected target with compounding monthly workload growth." /><Range label="Monthly growth" value={annualGrowth} onChange={setAnnualGrowth} /><div className="mt-6 rounded-2xl bg-sunken p-4"><p className="text-xs text-muted">12-month projected API spend</p><p className="mt-1 text-3xl font-semibold">{money(annual)}</p><p className="mt-1 text-xs text-muted">{target?.name}</p></div></article></Reveal>

      <Reveal className="lg:col-span-8" delay={60}><article className={cardClass}><ToolHeading number={19} icon={<Database className="size-4" />} title="Capability matrix" note="Scan published deployment and modality facts without opening each model page." /><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="text-xs text-muted"><tr><th className="pb-3">Model</th><th>Multimodal</th><th>Open weights</th><th>Context</th><th>Max output</th></tr></thead><tbody>{models.map((model) => <tr key={model.id} className="border-t border-rule"><th className="py-3 font-medium">{model.name}</th><td>{model.multimodal ? 'Yes' : 'No'}</td><td>{model.open_weights ? 'Yes' : 'No'}</td><td>{tokens(model.context_tokens)}</td><td>{tokens(model.max_output_tokens)}</td></tr>)}</tbody></table></div></article></Reveal>

      <Reveal className="lg:col-span-5"><article className={cardClass}><ToolHeading number={20} icon={<Gauge className="size-4" />} title="Value frontier" note="Highlights models where no other option has both lower cost and equal or larger context." /><div className="mt-5 space-y-3">{frontier.map((model) => <div key={model.id} className="rounded-2xl bg-sunken p-4"><div className="flex items-center gap-2"><Sparkles className="size-4 text-ai-models" /><strong className="text-sm">{model.name}</strong></div><p className="mt-1 text-xs text-muted">{money(monthlyCost(model))}/month · {tokens(model.context_tokens)} context</p></div>)}</div></article></Reveal>

      <Reveal className="lg:col-span-7" delay={60}><article className={cardClass}><ToolHeading number={21} icon={<Check className="size-4" />} title="Source and freshness audit" note="Shows the evidence coverage behind the current comparison snapshot." /><div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-2xl bg-sunken p-4"><p className="text-3xl font-semibold">{models.length * 2}</p><p className="text-xs text-muted">official links</p></div><div className="rounded-2xl bg-sunken p-4"><p className="text-xl font-semibold">{updatedAt}</p><p className="text-xs text-muted">snapshot date</p></div><div className="rounded-2xl bg-sunken p-4"><p className="text-3xl font-semibold">{models.every((model) => model.source_url && model.pricing_url) ? '100%' : 'Review'}</p><p className="text-xs text-muted">source coverage</p></div></div><ul className="mt-4 grid gap-2 sm:grid-cols-2">{models.map((model) => <li key={model.id} className="flex items-center gap-2 text-xs text-muted"><Check className="size-3 text-positive" /> {model.name}: model + pricing source</li>)}</ul></article></Reveal>

      <Reveal className="lg:col-span-5"><article className={cardClass}><ToolHeading number={22} icon={<FileText className="size-4" />} title="Private decision notes" note="Keep model-specific observations locally in this browser." /><select className={selectClass} value={noteModel} onChange={(event) => setNoteModel(event.target.value)}>{models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}</select><textarea value={notes[noteModel] ?? ''} onChange={(event) => setNotes((currentNotes) => ({ ...currentNotes, [noteModel]: event.target.value }))} placeholder="Latency tests, rollout risks, team feedback…" className="mt-3 min-h-32 w-full resize-y rounded-2xl border border-rule bg-paper p-3 text-sm" /></article></Reveal>

      <Reveal className="lg:col-span-7" delay={70}><article className={`${cardClass} overflow-hidden bg-[linear-gradient(135deg,var(--surface),var(--model-glow))]`}><ToolHeading number={23} icon={<Clipboard className="size-4" />} title="Decision brief" note="Turn your current assumptions into a concise handoff for your team." /><p className="mt-5 rounded-2xl border border-rule bg-paper/70 p-4 text-sm leading-relaxed text-muted">{brief}</p><div className="mt-4 flex flex-wrap gap-2"><Button size="sm" onClick={copyBrief}><Clipboard /> {copied ? 'Copied' : 'Copy brief'}</Button><Button size="sm" variant="outline" onClick={() => window.print()}><FileText /> Print report</Button></div></article></Reveal>
    </div>
  </section>
}
