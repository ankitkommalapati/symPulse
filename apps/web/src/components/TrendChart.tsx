import { useId, useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import type { ShiftDrift } from '../types';
import { day, number, percent } from '../lib/format';

export default function TrendChart({ trend }: { trend: ShiftDrift }) {
  const [index, setIndex] = useState(trend.series.length - 1);
  const id = useId();
  const points = trend.series;
  const selected = points[Math.min(Math.max(index, 0), points.length - 1)];
  if (!selected || !trend.baseline) return <div className="empty-chart">There isn’t enough complete history to establish a baseline.</div>;
  const max = Math.max(0.12, ...points.map(point => point.share || 0)) * 1.16;
  const width = 790, height = 228, left = 45, right = 15, top = 16, bottom = 32;
  const x = (i: number) => left + i / Math.max(1, points.length - 1) * (width - left - right);
  const y = (share: number) => height - bottom - share / max * (height - top - bottom);
  const commands: string[] = [];
  let penDown = false;
  points.forEach((point, i) => { if (point.share === null) { penDown = false; return; } commands.push(`${penDown ? 'L' : 'M'}${x(i).toFixed(1)},${y(point.share).toFixed(1)}`); penDown = true; });
  const baselineEnd = points.findIndex(point => point.date > trend.baseline!.end);
  const changeIndex = baselineEnd < 0 ? points.length - 1 : baselineEnd;
  const setSafe = (value: number) => setIndex(Math.max(0, Math.min(points.length - 1, value)));
  return <div className="trend-chart">
    <div className="chart-reading"><div><span>Selected work date</span><strong>{day(selected.date)}<small>{percent(selected.share)} overtime share</small></strong></div><div className="chart-reading-controls"><button aria-label="Previous chart date" onClick={() => setSafe(index - 1)} disabled={index <= 0}><ArrowLeft size={15} /></button><button aria-label="Next chart date" onClick={() => setSafe(index + 1)} disabled={index >= points.length - 1}><ArrowRight size={15} /></button></div></div>
    <div className="chart-interactive" tabIndex={0} role="group" aria-label="Overtime trend chart. Use left and right arrow keys to inspect dates."
      onKeyDown={event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); setSafe(index + (event.key === 'ArrowRight' ? 1 : -1)); } }}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${id}-title`} onMouseMove={event => { const box = event.currentTarget.getBoundingClientRect(); setSafe(Math.round(((event.clientX - box.left) / box.width * width - left) / (width - left - right) * (points.length - 1))); }}>
        <title id={`${id}-title`}>Overtime share by work date. Frozen baseline {percent(trend.baseline.mean_share)}.</title>
        <rect x={left} y={top} width={x(changeIndex) - left} height={height - top - bottom} fill="#f2f5f2" rx="4" />
        {[0, 0.25, 0.5, 0.75, 1].map(fraction => <g key={fraction}><line x1={left} x2={width - right} y1={y(max * fraction)} y2={y(max * fraction)} stroke="#e6ebe8" strokeDasharray="3 5" /><text x={left - 10} y={y(max * fraction) + 4} textAnchor="end" className="chart-axis">{number(max * fraction * 100)}%</text></g>)}
        <line x1={left} x2={width - right} y1={y(trend.baseline.mean_share)} y2={y(trend.baseline.mean_share)} stroke="#78a499" strokeDasharray="6 5" />
        <path d={commands.join(' ')} fill="none" stroke="#b0742f" strokeWidth="2.6" strokeLinejoin="round" />
        <line x1={x(index)} x2={x(index)} y1={top} y2={height - bottom} stroke="#456b60" strokeDasharray="2 4" />
        {selected.share !== null ? <circle cx={x(index)} cy={y(selected.share)} r="4.5" fill="#b0742f" stroke="white" strokeWidth="2" /> : null}
        {[0, Math.floor(points.length * 0.33), Math.floor(points.length * 0.66), points.length - 1].map(i => <text key={i} x={x(i)} y={height - 9} textAnchor="middle" className="chart-axis">{day(points[i].date)}</text>)}
      </svg>
    </div>
    <div className="chart-legend"><span><i className="legend-line amber-line" />Overtime share</span><span><i className="legend-dash" />Baseline average</span><span><i className="legend-square" />Frozen baseline period</span></div>
    <span className="sr-only" aria-live="polite">{day(selected.date)}: {percent(selected.share)} overtime share.</span>
  </div>;
}
