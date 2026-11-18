"use client";

import {
  Bar, BarChart, CartesianGrid, ErrorBar, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { CHART, axisProps, tooltipStyle } from "@/lib/chart-theme";

type Row = Record<string, unknown>;

export interface SeriesDef { key: string; label: string; color?: string; dashed?: boolean }

const fmtTick = (v: unknown) =>
  typeof v === "number" ? (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-US") : String(+v.toPrecision(4))) : String(v);

export function TimeLine({ data, x, series, height = 260, yDomain, yFormat, xFormat, reference, dots, legend = true }: {
  data: Row[]; x: string; series: SeriesDef[]; height?: number; yDomain?: [number | string, number | string]; dots?: boolean; legend?: boolean;
  yFormat?: (v: number) => string; xFormat?: (v: string) => string; reference?: { y: number; label: string };
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey={x} {...axisProps} minTickGap={28} tickFormatter={xFormat as never} />
          <YAxis {...axisProps} width={56} domain={yDomain || ["auto", "auto"]} tickFormatter={(yFormat || fmtTick) as never} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => (yFormat ? yFormat(v) : fmtTick(v))} labelFormatter={xFormat as never} />
          {legend && series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: CHART.text }} />}
          {reference && <ReferenceLine y={reference.y} stroke={CHART.axis} strokeDasharray="4 4" label={{ value: reference.label, fill: CHART.text, fontSize: 11, position: "insideTopRight" }} />}
          {series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color || CHART.series[i]} strokeWidth={1.8}
              strokeDasharray={s.dashed ? "5 4" : undefined} dot={dots || data.length <= 12 ? { r: 3, fill: s.color || CHART.series[i], strokeWidth: 0 } : false} connectNulls={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Bars({ data, x, series, height = 260, layout = "horizontal", yFormat, stacked }: {
  data: Row[]; x: string; series: SeriesDef[]; height?: number; layout?: "horizontal" | "vertical";
  yFormat?: (v: number) => string; stacked?: boolean;
}) {
  const vertical = layout === "vertical";
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, left: vertical ? 8 : 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={vertical} horizontal={!vertical} />
          {/* Recharts 2 only finds axes that are direct children, so no fragments here. */}
          {vertical
            ? <XAxis type="number" {...axisProps} tickFormatter={(yFormat || fmtTick) as never} />
            : <XAxis dataKey={x} {...axisProps} minTickGap={12} />}
          {vertical
            ? <YAxis type="category" dataKey={x} {...axisProps} width={96} />
            : <YAxis {...axisProps} width={56} tickFormatter={(yFormat || fmtTick) as never} />}
          <Tooltip {...tooltipStyle} formatter={(v: number) => (yFormat ? yFormat(v) : fmtTick(v))} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: CHART.text }} />}
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color || CHART.series[i]} radius={vertical ? [0, 3, 3, 0] : [3, 3, 0, 0]}
              stackId={stacked ? "s" : undefined} isAnimationActive={false} maxBarSize={36} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Points with 95% interval whiskers (e.g. win rates with Wilson intervals). */
export function IntervalBars({ data, x, y, low, high, height = 260, reference, yFormat }: {
  data: Row[]; x: string; y: string; low: string; high: string; height?: number; reference?: number;
  yFormat?: (v: number) => string;
}) {
  const rows = data.map((d) => ({ ...d, _err: [(d[y] as number) - (d[low] as number), (d[high] as number) - (d[y] as number)] }));
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey={x} {...axisProps} />
          <YAxis {...axisProps} width={56} domain={["auto", "auto"]} tickFormatter={(yFormat || fmtTick) as never} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => (yFormat ? yFormat(v) : fmtTick(v))} />
          {reference !== undefined && <ReferenceLine y={reference} stroke={CHART.axis} strokeDasharray="4 4" />}
          <Bar dataKey={y} fill={CHART.cyan} fillOpacity={0.25} stroke={CHART.cyan} maxBarSize={28} isAnimationActive={false}>
            <ErrorBar dataKey="_err" width={6} stroke={CHART.text} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ScatterPlot({ data, x, y, xLabel, yLabel, height = 280, diagonal, format, xDomain = [0, 1], yDomain = [0, 1] }: {
  data: Row[]; x: string; y: string; xLabel: string; yLabel: string; height?: number; diagonal?: boolean;
  format?: (v: number) => string; xDomain?: [number | string, number | string]; yDomain?: [number | string, number | string];
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 16 }}>
          <CartesianGrid stroke={CHART.grid} />
          <XAxis type="number" dataKey={x} name={xLabel} {...axisProps} domain={xDomain} tickFormatter={(format || fmtTick) as never}
            label={{ value: xLabel, position: "insideBottom", offset: -10, fill: CHART.text, fontSize: 11 }} />
          <YAxis type="number" dataKey={y} name={yLabel} {...axisProps} width={56} domain={yDomain} tickFormatter={(format || fmtTick) as never}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: CHART.text, fontSize: 11 }} />
          <ZAxis range={[18, 18]} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => (format ? format(v) : fmtTick(v))} />
          {diagonal && <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={CHART.axis} strokeDasharray="4 4" />}
          <Scatter data={data} fill={CHART.cyan} fillOpacity={0.55} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Reliability diagram: mean predicted vs observed frequency per bin, for several models. */
export function Reliability({ models, height = 300 }: {
  models: { label: string; bins: { mean_predicted: number | null; observed_frequency: number | null; n: number }[] }[];
  height?: number;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 16 }}>
          <CartesianGrid stroke={CHART.grid} />
          <XAxis type="number" dataKey="mean_predicted" name="Mean predicted" {...axisProps} domain={[0, 1]}
            label={{ value: "Predicted probability (blue win)", position: "insideBottom", offset: -10, fill: CHART.text, fontSize: 11 }} />
          <YAxis type="number" dataKey="observed_frequency" name="Observed" {...axisProps} width={56} domain={[0, 1]}
            label={{ value: "Observed frequency", angle: -90, position: "insideLeft", fill: CHART.text, fontSize: 11 }} />
          <ZAxis type="number" dataKey="n" range={[20, 220]} name="Games" />
          <Tooltip {...tooltipStyle} formatter={(v: number) => (typeof v === "number" ? +v.toFixed(3) : v)} />
          <Legend wrapperStyle={{ fontSize: 12, color: CHART.text }} verticalAlign="top" />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={CHART.axis} strokeDasharray="4 4" />
          {models.map((m, i) => (
            <Scatter key={m.label} name={m.label} data={m.bins.filter((b) => b.n > 0)} fill={CHART.series[i]}
              line={{ stroke: CHART.series[i], strokeWidth: 1.2 }} isAnimationActive={false} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Several curves on numeric axes, each with its own points (e.g. ROC curves). */
export function Curves({ curves, x, y, xLabel, yLabel, height = 280, diagonal }: {
  curves: { label: string; points: Row[] }[]; x: string; y: string; xLabel: string; yLabel: string;
  height?: number; diagonal?: boolean;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart margin={{ top: 8, right: 12, left: 0, bottom: 16 }}>
          <CartesianGrid stroke={CHART.grid} />
          <XAxis type="number" dataKey={x} domain={[0, 1]} {...axisProps}
            label={{ value: xLabel, position: "insideBottom", offset: -10, fill: CHART.text, fontSize: 11 }} />
          <YAxis type="number" domain={[0, 1]} {...axisProps} width={56}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: CHART.text, fontSize: 11 }} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => (typeof v === "number" ? v.toFixed(3) : v)} />
          <Legend wrapperStyle={{ fontSize: 12, color: CHART.text }} verticalAlign="top" />
          {diagonal && <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={CHART.axis} strokeDasharray="4 4" />}
          {curves.map((c, i) => (
            <Line key={c.label} data={c.points} dataKey={y} name={c.label} stroke={CHART.series[i]} dot={false}
              strokeWidth={1.6} isAnimationActive={false} type="linear" />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
