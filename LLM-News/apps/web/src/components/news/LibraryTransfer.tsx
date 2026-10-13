import { Download, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { library, useLibrary } from '@/lib/library'
import { exportLibrary, MAX_IMPORT_BYTES } from '@/lib/libraryTransfer'

export function LibraryTransfer() {
  const data = useLibrary()
  const fileInput = useRef<HTMLInputElement>(null)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const download = () => {
    const url = URL.createObjectURL(new Blob([exportLibrary(data)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `newssense-library-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const upload = async (file?: File) => {
    if (!file) return
    setBusy(true)
    try {
      if (file.size > MAX_IMPORT_BYTES) throw new Error('Choose a library backup smaller than 2 MB.')
      library.import(await file.text())
      setFeedback({ error: false, message: 'Library imported. Your saved stories, story follows and topics have been merged.' })
    } catch (error) {
      setFeedback({ error: true, message: error instanceof Error ? error.message : 'Could not read this backup.' })
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  return (
    <section aria-label="Library backup" className="space-y-3 rounded-2xl border border-rule p-5">
      <h2 className="font-semibold">Take your library with you</h2>
      <p className="text-sm text-muted">Export saved stories, followed stories and topics, then import the backup in another browser. Existing stories stay saved.</p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={download}><Download /> Export library</Button>
        <Button onClick={() => fileInput.current?.click()} disabled={busy}><Upload /> {busy ? 'Importing…' : 'Import library'}</Button>
        <input ref={fileInput} type="file" accept=".json,application/json" aria-label="Library backup file" className="sr-only"
          onChange={(event) => { void upload(event.target.files?.[0]) }} />
      </div>
      {feedback && <p role={feedback.error ? 'alert' : 'status'} className={`text-sm ${feedback.error ? 'text-negative' : 'text-positive'}`}>{feedback.message}</p>}
    </section>
  )
}
