import { useEffect, useState, type ReactNode } from 'react'
import type { TooltipContentProps } from 'recharts'

const TOKENS = [
  'series-social', 'series-tech', 'series-entertainment', 'series-magnitude',
  'series-positive', 'series-negative', 'rule', 'faint', 'muted', 'surface', 'sunken', 'ink',
] as const
export type ChartColors = Record<(typeof TOKENS)[number], string>

const read = (): ChartColors => {
  const style = getComputedStyle(document.documentElement)
  return Object.fromEntries(TOKENS.map((t) => [t, style.getPropertyValue(`--${t}`).trim()])) as ChartColors
}

/** Theme colours as concrete values (SVG attributes can't resolve CSS variables); follows the theme toggle. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState(read)
  useEffect(() => {
    const observer = new MutationObserver(() => setColors(read()))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return colors
}

export const seriesColor = (colors: ChartColors, category: string) =>
  colors[`series-${category}` as keyof ChartColors] ?? colors.faint

export const axisProps = (colors: ChartColors) => ({
  tick: { fill: colors.muted, fontSize: 12 },
  axisLine: false,
  tickLine: false,
})

/** Value-first tooltip rows with line keys (dataviz interaction spec). */
export function ChartTooltip({
  active,
  payload,
  label,
  format = (v) => String(v),
}: Partial<TooltipContentProps> & { format?: (value: number) => string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="min-w-36 rounded-xl border border-rule bg-surface px-3 py-2 text-sm shadow-lg">
      {label !== undefined && <p className="mb-1 text-xs text-faint">{label}</p>}
      {payload.map((entry) => (
        <p key={String(entry.dataKey ?? entry.name)} className="flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-3 rounded" style={{ background: entry.color }} />
          <strong className="font-semibold tabular-nums">{format(Number(entry.value))}</strong>
          <span className="text-muted">{entry.name}</span>
        </p>
      ))}
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: item.color }} />
          {item.label}
        </li>
      ))}
    </ul>
  )
}

export interface DataTable {
  columns: string[]
  rows: (string | number)[][]
}

/** Card for one chart; every chart also offers its numbers as a table (never colour-only). */
export function ChartCard({
  title,
  subtitle,
  table,
  children,
  className,
}: {
  title: string
  subtitle?: string
  table?: DataTable
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-2xl border border-rule bg-surface p-5 ${className ?? ''}`}>
      <h2 className="font-semibold">{title}</h2>
      {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      <div className="mt-5">{children}</div>
      {table && table.rows.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Show data table</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-rule text-xs text-faint">
                  {table.columns.map((column) => (
                    <th key={column} className="py-1.5 pr-4 font-medium">{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, i) => (
                  <tr key={i} className="border-b border-rule last:border-0">
                    {row.map((cell, j) => (
                      <td key={j} className="py-1.5 pr-4 tabular-nums">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  )
}

export function StatTile({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-rule bg-surface p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      {note && <div className="mt-1 text-xs text-faint">{note}</div>}
    </div>
  )
}
