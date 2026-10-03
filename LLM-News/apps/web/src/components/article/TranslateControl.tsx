import { Languages, LoaderCircle, Undo2 } from 'lucide-react'
import { useLanguages, useTranslate } from '@/api/queries'
import type { Article } from '@/api/types'
import { Button } from '@/components/ui/button'

interface Props {
  date: string
  groupId: string
  translatedTo?: string
  onTranslated: (article: Article) => void
  onShowOriginal: () => void
}

export function TranslateControl({ date, groupId, translatedTo, onTranslated, onShowOriginal }: Props) {
  const languages = useLanguages()
  const translate = useTranslate()

  if (translatedTo) {
    return (
      <Button onClick={onShowOriginal} aria-label="Show the original English article">
        <Undo2 /> {translatedTo} · Show original
      </Button>
    )
  }

  if (translate.isPending) {
    return (
      <span role="status" className="flex h-10 items-center gap-2 rounded-full border border-rule px-4 text-sm text-muted">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        Translating… this takes about 30 seconds
      </span>
    )
  }

  const options = Object.entries(languages.data?.languages ?? {}).filter(([code]) => code !== 'en')

  return (
    <div className="flex flex-col gap-1">
      <label className="relative flex h-10 items-center rounded-full border border-rule bg-surface pr-3 pl-3 text-sm hover:bg-sunken">
        <Languages className="pointer-events-none size-4 text-muted" aria-hidden />
        <span className="sr-only">Translate this article</span>
        <select
          value=""
          disabled={!options.length}
          onChange={(event) => {
            const language = event.target.value
            if (language) translate.mutate({ date, groupId, language }, { onSuccess: (r) => onTranslated(r.translation) })
          }}
          className="appearance-none bg-transparent pr-1 pl-2 font-medium text-ink outline-none"
        >
          <option value="">Translate</option>
          {options.map(([code, name]) => (
            <option key={code} value={code}>
              {name}
            </option>
          ))}
        </select>
      </label>
      {translate.error && <p className="text-xs text-negative">{translate.error.message}</p>}
    </div>
  )
}
