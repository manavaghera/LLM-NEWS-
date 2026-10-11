import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import type { ReaderReport, ReportStatus } from '@/api/types'
import { Button } from '@/components/ui/button'

function ReportCard({ report, token, onChange }: { report: ReaderReport; token: string; onChange: (report: ReaderReport) => void }) {
  const client = useQueryClient()
  const [resolution, setResolution] = useState(report.resolution)
  const [correction, setCorrection] = useState('')
  const [pending, setPending] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; message: string } | null>(null)
  const update = async (status: ReportStatus, publish = false) => {
    setPending(true)
    setFeedback(null)
    try {
      if (publish) {
        const result = await api.publishCorrection(token, report.id, correction.trim())
        onChange({ ...report, status: 'resolved', resolution: result.correction.text, resolved_at: result.correction.created_at })
        setResolution(result.correction.text)
        setCorrection('')
        void client.invalidateQueries({ queryKey: ['corrections', report.date, report.group_id] })
      } else {
        onChange((await api.resolveReport(token, report.id, status, resolution.trim())).report)
      }
      setFeedback({ error: false, message: publish ? 'Correction published and report resolved.' : 'Report updated.' })
    } catch (error) {
      setFeedback({ error: true, message: error instanceof Error ? error.message : 'Could not update this report.' })
    } finally { setPending(false) }
  }
  return (
    <article className="space-y-4 rounded-2xl border border-rule bg-surface p-5">
      <div>
        <h3 className="font-semibold">Report #{report.id} · {report.status}</h3>
        <p className="mt-1 text-xs text-muted">{new Date(report.created_at).toLocaleString()} · {report.kind.replaceAll('_', ' ')}</p>
        {report.original_headline && <p className="mt-1 text-sm text-muted">Original story: {report.original_headline}</p>}
        <Link to={`/article/${report.date}/${report.group_id}`} className="text-sm text-accent hover:underline">Read article · {report.date}/{report.group_id} →</Link>
      </div>
      <p className="whitespace-pre-wrap break-words text-sm">{report.message}</p>
      {report.article_matches === false && <p className="rounded-xl bg-sunken p-3 text-sm text-negative">This article location now belongs to a different story, or the original identity could not be verified. Publishing is disabled; you can still resolve or dismiss this report.</p>}
      <label className="block space-y-1 text-sm font-medium">Private resolution note
        <textarea rows={2} maxLength={2000} value={resolution} onChange={(e) => setResolution(e.target.value)} className="block w-full rounded-xl border border-rule bg-paper p-3 font-normal" />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => { void update('resolved') }} disabled={pending}>Resolve report</Button>
        <Button onClick={() => { void update('dismissed') }} disabled={pending}>Dismiss report</Button>
        {report.status !== 'open' && <Button onClick={() => { void update('open') }} disabled={pending}>Reopen report</Button>}
      </div>
      <details className="border-t border-rule pt-3">
        <summary className="cursor-pointer text-sm font-medium text-accent">Publish an article correction</summary>
        <p className="mt-2 text-xs text-muted">This note becomes visible on the article and resolves this report. Check the sources before publishing.</p>
        <label className="mt-3 block space-y-1 text-sm font-medium">Public correction
          <textarea rows={3} minLength={5} maxLength={3000} value={correction} onChange={(e) => setCorrection(e.target.value)} className="block w-full rounded-xl border border-rule bg-paper p-3 font-normal" />
        </label>
        <Button variant="primary" className="mt-3" disabled={pending || report.article_matches === false || correction.trim().length < 5} onClick={() => { void update('resolved', true) }}>Publish correction</Button>
      </details>
      {feedback && <p role={feedback.error ? 'alert' : 'status'} className={`text-sm ${feedback.error ? 'text-negative' : 'text-positive'}`}>{feedback.message}</p>}
    </article>
  )
}

export function ReportsPanel({ reports, token, onChange }: { reports: ReaderReport[]; token: string; onChange: (report: ReaderReport) => void }) {
  const [filter, setFilter] = useState<ReportStatus | 'all'>('open')
  const visible = reports.filter((report) => filter === 'all' || report.status === filter)
  return (
    <section aria-labelledby="reader-reports" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="reader-reports" className="text-lg font-semibold">Reader reports ({reports.filter((r) => r.status === 'open').length} open)</h2>
        <label className="text-sm">Report status <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} className="ml-2 h-9 rounded-full border border-rule bg-surface px-3">
          {['open', 'resolved', 'dismissed', 'all'].map((status) => <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>)}
        </select></label>
      </div>
      <p className="text-xs text-muted">Showing the latest {reports.length} reports. Private notes stay in the review inbox; published corrections appear on the article.</p>
      {!visible.length && <p className="rounded-xl bg-sunken p-4 text-sm text-muted">No {filter === 'all' ? '' : `${filter} `}reports.</p>}
      {visible.map((report) => <ReportCard key={report.id} report={report} token={token} onChange={onChange} />)}
    </section>
  )
}
