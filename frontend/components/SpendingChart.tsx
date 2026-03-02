'use client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { SpendingTimeSeries } from '@/types/api';
import { formatUSD } from '@/lib/utils';

export function SpendingChart({ data }: { data: SpendingTimeSeries[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 24, left: 16, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={formatUSD} />
        <Tooltip formatter={(v: number | undefined) => v != null ? formatUSD(v) : ''} />
        <Line
          type="monotone"
          dataKey="total_obligated"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          name="Total Obligated"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
