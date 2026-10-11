import { AlertTriangle, CheckCircle2, Newspaper, Sparkles, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { api } from '@/api/client'
import { useModelCatalog, useUpdateStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { CATEGORIES } from '@/lib/format'
import { library, useLibrary } from '@/lib/library'

const ONBOARDING_KEY = 'newssense-onboarding-v1'
const MODEL_KEY = 'newssense-preferred-models'

export function PageAnalytics() {
  const location = useLocation()
  useEffect(() => { void api.analytics('page_view').catch(() => undefined) }, [location.pathname])
  useEffect(() => {
    const known = localStorage.getItem('newssense-visited') === 'yes'
    if (known && sessionStorage.getItem('newssense-return-counted') !== 'yes') {
      sessionStorage.setItem('newssense-return-counted', 'yes')
      void api.analytics('return_visit').catch(() => undefined)
    }
    localStorage.setItem('newssense-visited', 'yes')
  }, [])
  return null
}

export function StaleNewsBanner() {
  const { data } = useUpdateStatus()
  if (!data?.stale) return null
  return (
    <div aria-live="polite" className="border-b border-amber-400/30 bg-amber-400/10 px-4 py-2 text-center text-sm text-ink">
      <AlertTriangle className="mr-2 inline size-4 text-amber-600" aria-hidden />
      {data.last_update
        ? `News has not updated for ${data.minutes_since_update ?? 'several'} minutes. The last published edition is still available while the updater recovers.`
        : 'The hourly news updater has not reported a successful run yet.'}
    </div>
  )
}

export function FirstVisitGuide() {
  const models = useModelCatalog().data?.models ?? []
  const saved = useLibrary()
  const [open, setOpen] = useState(() => typeof window !== 'undefined' && localStorage.getItem(ONBOARDING_KEY) !== 'done')
  const [categories, setCategories] = useState<string[]>([])
  const [modelIds, setModelIds] = useState<string[]>([])
  if (!open || import.meta.env.VITE_E2E === 'true') return null
  const toggle = (list: string[], value: string, set: (next: string[]) => void) => set(list.includes(value) ? list.filter((item) => item !== value) : [...list, value])
  const finish = () => {
    categories.forEach((category) => { if (!saved.categories.includes(category)) library.toggleCategory(category) })
    localStorage.setItem(MODEL_KEY, JSON.stringify(modelIds))
    localStorage.setItem(ONBOARDING_KEY, 'done')
    void api.analytics('onboarding_completed').catch(() => undefined)
    setOpen(false)
  }
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-black/55 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
      <div className="relative my-6 w-full max-w-2xl rounded-3xl border border-rule bg-paper p-6 shadow-2xl sm:p-8">
        <button type="button" onClick={finish} className="absolute right-4 top-4 rounded-full p-2 text-muted hover:bg-sunken" aria-label="Close welcome guide"><X className="size-5" /></button>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">Welcome to NewsSense</p>
        <h2 id="welcome-title" className="headline mt-2 text-3xl font-semibold">Choose what you want to follow</h2>
        <p className="mt-2 text-muted">Your choices stay in this browser. You can change topics later from Saved.</p>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-sunken p-4 text-sm"><CheckCircle2 className="mb-2 size-5 text-positive" /><strong>Verified report</strong><p className="mt-1 text-muted">Claims passed the source check and include evidence.</p></div>
          <div className="rounded-2xl bg-sunken p-4 text-sm"><Newspaper className="mb-2 size-5 text-accent" /><strong>Reported or rumour</strong><p className="mt-1 text-muted">Unconfirmed model news stays clearly labelled.</p></div>
          <div className="rounded-2xl bg-sunken p-4 text-sm"><Sparkles className="mb-2 size-5 text-ai-models" /><strong>Model scores</strong><p className="mt-1 text-muted">Preference tools use price and context data, not invented quality claims.</p></div>
        </div>
        <fieldset className="mt-6"><legend className="font-semibold">Preferred topics</legend><div className="mt-3 flex flex-wrap gap-2">{CATEGORIES.map((category) => <button type="button" key={category.value} aria-pressed={categories.includes(category.value)} onClick={() => toggle(categories, category.value, setCategories)} className={`rounded-full border px-3 py-1.5 text-sm ${categories.includes(category.value) ? 'border-accent bg-accent text-accent-ink' : 'border-rule'}`}>{category.label}</button>)}</div></fieldset>
        {!!models.length && <fieldset className="mt-6"><legend className="font-semibold">AI models to watch</legend><div className="mt-3 flex flex-wrap gap-2">{models.map((model) => <button type="button" key={model.id} aria-pressed={modelIds.includes(model.id)} onClick={() => toggle(modelIds, model.id, setModelIds)} className={`rounded-full border px-3 py-1.5 text-sm ${modelIds.includes(model.id) ? 'border-ai-models bg-sunken' : 'border-rule'}`}>{model.name}</button>)}</div></fieldset>}
        <div className="mt-7 flex justify-end"><Button variant="primary" onClick={finish}>Start reading</Button></div>
      </div>
    </div>
  )
}
