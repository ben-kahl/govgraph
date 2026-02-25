'use client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { MarketShareEntry } from '@/types/api';

function formatMillions(value: number) {
  return `$${(value / 1_000_000).toFixed(1)}M`;
}

export function MarketShareChart({ data }: { data: MarketShareEntry[] }) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} margin={{ top: 8, right: 24, left: 16, bottom: 80 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="canonical_name"
          tick={{ fontSize: 11 }}
          angle={-40}
          textAnchor="end"
          interval={0}
        />
        <YAxis tickFormatter={formatMillions} />
        <Tooltip formatter={(v: number | undefined) => v != null ? formatMillions(v) : ''} />
        <Bar dataKey="total_obligated" fill="#3b82f6" name="Total Obligated" />
      </BarChart>
    </ResponsiveContainer>
  );
}
