import * as Dialog from '@radix-ui/react-dialog'
import { Check, Flag, LoaderCircle, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useReport } from '@/api/queries'
import type { ReportKind } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const KINDS: { value: ReportKind; label: string }[] = [
  { value: 'wrong_fact', label: 'A fact is wrong' },
  { value: 'bad_source', label: "A source doesn't say this" },
  { value: 'missing_context', label: 'Important context is missing' },
  { value: 'other', label: 'Something else' },
]

/** Lets a reader flag an error; reports feed the accuracy numbers on the Trends page */
export function ReportProblem({ date, groupId }: { date: string; groupId: string }) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState<ReportKind>('wrong_fact')
  const [message, setMessage] = useState('')
  const report = useReport()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    report.mutate({ date, group_id: groupId, kind, message: message.trim() })
  }
  const onOpenChange = (next: boolean) => {
    setOpen(next)
    if (!next && report.isSuccess) {
      report.reset()
      setMessage('')
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="sm">
          <Flag /> Report a problem
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-rule bg-surface p-6 shadow-2xl">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Report a problem</Dialog.Title>
              <Dialog.Description className="text-sm text-muted">
                Tell us what&apos;s wrong with this article. Nothing about you is stored.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close"><X /></Button>
            </Dialog.Close>
          </div>

          {report.isSuccess ? (
            <div role="status" className="flex flex-col items-center gap-3 py-6 text-center">
              <Check className="size-8 text-positive" aria-hidden />
              <p className="font-medium">Thanks, your report was sent.</p>
              <Dialog.Close asChild><Button>Close</Button></Dialog.Close>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <fieldset className="space-y-2">
                <legend className="mb-1 text-sm font-medium">What&apos;s the problem?</legend>
                {KINDS.map((k) => (
                  <label key={k.value} className={cn('flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm',
                    kind === k.value ? 'border-accent bg-accent-soft/50' : 'border-rule hover:bg-sunken')}>
                    <input type="radio" name="kind" value={k.value} checked={kind === k.value} onChange={() => setKind(k.value)}
                      className="accent-[var(--accent)]" />
                    {k.label}
                  </label>
                ))}
              </fieldset>
              <label className="block text-sm font-medium">
                Details
                <textarea
                  required
                  minLength={5}
                  maxLength={1000}
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="What is wrong, and what is correct (with a link if you have one)?"
                  className="mt-1 block w-full rounded-xl border border-rule bg-paper p-3 text-sm font-normal placeholder:text-faint"
                />
              </label>
              {report.error && <p role="alert" className="text-sm text-negative">{report.error.message}</p>}
              <Button type="submit" variant="primary" className="w-full" disabled={report.isPending || message.trim().length < 5}>
                {report.isPending ? <LoaderCircle className="animate-spin" /> : <Flag />} Send report
              </Button>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
