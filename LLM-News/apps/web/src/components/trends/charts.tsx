import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { axisProps, ChartTooltip, Legend, seriesColor, useChartColors } from './chartKit'

/** Single-series horizontal bars (magnitude): one hue, value at the bar tip, rounded data-end. */
export function HorizontalBars({ data, valueLabel }: { data: { name: string; value: number }[]; valueLabel: string }) {
  const colors = useChartColors()
  const height = Math.max(120, data.length * 34 + 16)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={130} {...axisProps(colors)} tick={{ fill: colors.ink, fontSize: 13 }} />
        <Tooltip cursor={{ fill: colors.sunken }} content={(props) => <ChartTooltip {...props} />} />
        <Bar dataKey="value" name={valueLabel} fill={colors['series-magnitude']} radius={[0, 4, 4, 0]} maxBarSize={20} isAnimationActive={false}>
          <LabelList dataKey="value" position="right" fill={colors.muted} fontSize={12} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Articles per category per day: stacked columns (part-to-whole), 2px surface gaps between segments. */
export function StackedColumns({
  data,
  categories,
}: {
  data: Record<string, number | string | null>[]
  categories: { value: string; label: string }[]
}) {
  const colors = useChartColors()
  return (
    <div className="space-y-3">
      <Legend items={categories.map((c) => ({ label: c.label, color: seriesColor(colors, c.value) }))} />
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={colors.rule} />
          <XAxis dataKey="label" {...axisProps(colors)} />
          <YAxis allowDecimals={false} {...axisProps(colors)} />
          <Tooltip cursor={{ fill: colors.sunken }} content={(props) => <ChartTooltip {...props} />} />
          {categories.map((c, i) => (
            <Bar
              key={c.value}
              dataKey={c.value}
              name={c.label}
              stackId="articles"
              fill={seriesColor(colors, c.value)}
              stroke={colors.surface}
              strokeWidth={2}
              maxBarSize={24}
              radius={i === categories.length - 1 ? [4, 4, 0, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Average tone per category over time: 2px lines on a -1..1 scale with a zero baseline. */
export function ToneLines({
  data,
  categories,
}: {
  data: Record<string, number | string | null>[]
  categories: { value: string; label: string }[]
}) {
  const colors = useChartColors()
  return (
    <div className="space-y-3">
      <Legend items={categories.map((c) => ({ label: c.label, color: seriesColor(colors, c.value) }))} />
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={colors.rule} />
          <XAxis dataKey="label" {...axisProps(colors)} />
          <YAxis domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} {...axisProps(colors)} />
          <ReferenceLine y={0} stroke={colors.faint} />
          <Tooltip
            cursor={{ stroke: colors.faint, strokeWidth: 1 }}
            content={(props) => <ChartTooltip {...props} format={(v) => v.toFixed(2)} />}
          />
          {categories.map((c) => (
            <Line
              key={c.value}
              dataKey={c.value}
              name={c.label}
              stroke={seriesColor(colors, c.value)}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, stroke: colors.surface, fill: seriesColor(colors, c.value) }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: colors.surface }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
