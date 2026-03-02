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
import type { MarketShareEntry, AgencyMarketShareEntry } from '@/types/api';
import { formatUSD } from '@/lib/utils';

export function MarketShareChart({
  data,
  nameKey = 'canonical_name',
}: {
  data: MarketShareEntry[] | AgencyMarketShareEntry[];
  nameKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} margin={{ top: 8, right: 24, left: 16, bottom: 80 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey={nameKey}
          tick={{ fontSize: 11 }}
          angle={-40}
          textAnchor="end"
          interval={0}
        />
        <YAxis tickFormatter={formatUSD} />
        <Tooltip formatter={(v: number | undefined) => v != null ? formatUSD(v) : ''} />
        <Bar dataKey="total_obligated" fill="#3b82f6" name="Total Obligated" />
      </BarChart>
    </ResponsiveContainer>
  );
}
