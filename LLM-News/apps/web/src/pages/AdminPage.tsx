import { LogOut, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, api } from '@/api/client'
import type { Operations, ReaderReport } from '@/api/types'
import { OperationsPanel } from '@/components/admin/OperationsPanel'
import { ReportsPanel } from '@/components/admin/ReportsPanel'
import { Button } from '@/components/ui/button'

export function AdminPage() {
  const [draft, setDraft] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [signedIn, setSignedIn] = useState(false)
  const [operations, setOperations] = useState<Operations | null>(null)
  const [reports, setReports] = useState<ReaderReport[]>([])
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const revision = useRef(0)
  const load = useCallback(async () => {
    const request = ++revision.current
    setPending(true)
    setError('')
    try {
      const [health, inbox] = await Promise.all([api.operations(), api.reports()])
      if (request !== revision.current) return
      setSignedIn(true)
      setDraft('')
      setOperations(health)
      setReports(inbox.reports)
    } catch (failure) {
      if (request !== revision.current) return
      setError(failure instanceof ApiError && failure.status === 404 ? 'Your administrator session is unavailable.' : failure instanceof Error ? failure.message : 'Could not load the dashboard.')
    } finally { if (request === revision.current) setPending(false) }
  }, [])
  useEffect(() => {
    if (!signedIn) return
    const timer = setInterval(() => { void load() }, 60_000)
    return () => clearInterval(timer)
  }, [load, signedIn])
  useEffect(() => { api.adminSession().then(() => load()).catch(() => undefined) }, [load])
  useEffect(() => () => { revision.current++ }, [])
  const signIn = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft.trim() && (!username.trim() || !password)) return
    setPending(true); setError('')
    try {
      if (draft.trim()) await api.adminLogin(draft.trim())
      else await api.adminAccountLogin(username.trim(), password, otp.trim())
      setPassword(''); setOtp(''); await load()
    }
    catch (failure) { setError(failure instanceof ApiError && [401, 404].includes(failure.status) ? 'Could not sign in. Check your credentials and one-time code.' : failure instanceof Error ? failure.message : 'Could not sign in.'); setPending(false) }
  }
  const signOut = () => {
    revision.current++
    void api.adminLogout().catch(() => undefined)
    setSignedIn(false); setDraft(''); setUsername(''); setPassword(''); setOtp(''); setOperations(null); setReports([]); setError(''); setPending(false)
  }
  return (
    <div className="space-y-8">
      <title>Owner dashboard · NewsSense</title>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="headline text-4xl font-semibold">Owner dashboard</h1><p className="mt-2 text-sm text-muted">Review reader reports, publish corrections and check the news pipeline.</p></div>
        {signedIn && <div className="flex gap-2"><Button onClick={() => { void load() }} disabled={pending}><RefreshCw /> Refresh</Button><Button onClick={signOut}><LogOut /> Sign out</Button></div>}
      </div>
      {!signedIn && <form onSubmit={signIn} className="max-w-lg space-y-4 rounded-2xl border border-rule bg-surface p-6">
        <p className="text-sm text-muted">Sign in with your named administrator account. Sessions use an HTTP-only cookie and expire after eight hours.</p>
        <label className="block space-y-1 text-sm font-medium">Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" className="block h-11 w-full rounded-xl border border-rule bg-paper px-3" />
        </label>
        <label className="block space-y-1 text-sm font-medium">Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="block h-11 w-full rounded-xl border border-rule bg-paper px-3" />
        </label>
        <label className="block space-y-1 text-sm font-medium">Authenticator code <span className="font-normal text-muted">(when enabled)</span>
          <input inputMode="numeric" pattern="[0-9]*" value={otp} onChange={(e) => setOtp(e.target.value)} autoComplete="one-time-code" className="block h-11 w-full rounded-xl border border-rule bg-paper px-3" />
        </label>
        <details open className="text-sm text-muted"><summary className="cursor-pointer">Legacy token access</summary>
          <label className="mt-3 block space-y-1 font-medium text-ink">Admin token
            <input type="password" value={draft} onChange={(e) => setDraft(e.target.value)} autoComplete="off" className="block h-11 w-full rounded-xl border border-rule bg-paper px-3" />
          </label>
        </details>
        <Button type="submit" variant="primary" disabled={pending || (!draft.trim() && (!username.trim() || !password))}>{pending ? 'Signing in…' : 'Sign in'}</Button>
      </form>}
      {error && <p role="alert" className="rounded-xl bg-negative/10 p-4 text-sm text-negative">{error}</p>}
      {signedIn && operations && <>
        <OperationsPanel data={operations} token="" onBudget={(usage) => setOperations((prev) => prev ? { ...prev, usage } : prev)} />
        <ReportsPanel reports={reports} token="" onChange={(report) => setReports((prev) => prev.map((r) => r.id === report.id ? report : r))} />
      </>}
    </div>
  )
}
