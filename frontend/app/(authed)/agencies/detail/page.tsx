'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '@/lib/api';
import { formatUSD } from '@/lib/utils';
import { SpendingChart } from '@/components/SpendingChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';

function KpiCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <p className="text-xs text-muted-foreground">{title}</p>
        <p className="text-2xl font-bold mt-0.5">{value}</p>
      </CardContent>
    </Card>
  );
}

function AgencyDetail() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') ?? '';
  const [period, setPeriod] = useState<'month' | 'quarter' | 'year'>('month');

  const { data: agency, isLoading: aLoading } = useQuery({
    queryKey: ['agency', id],
    queryFn: () => api.agencies.getById(id),
    enabled: !!id,
  });

  const { data: stats } = useQuery({
    queryKey: ['agencyStats', id],
    queryFn: () => api.agencies.stats(id),
    enabled: !!id,
  });

  const { data: concentration } = useQuery({
    queryKey: ['agencyConcentration', id],
    queryFn: () => api.agencies.vendorConcentration(id),
    enabled: !!id,
  });

  const { data: spending, isLoading: sLoading } = useQuery({
    queryKey: ['agencySpending', id, period],
    queryFn: () => api.analytics.spendingOverTime(id, period),
    enabled: !!id,
  });

  if (aLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!agency) return <p className="text-destructive">Agency not found.</p>;

  const hhiEntry = concentration?.find((c) => c.agency_name === agency.agency_name) ?? concentration?.[0];
  const hhiScore = hhiEntry?.hhi ?? null;

  const topVendors = stats?.top_vendors ?? [];
  const spendByYear = (stats?.spending_by_year ?? [])
    .slice()
    .sort((a, b) => a.year - b.year)
    .map((y) => ({ name: String(y.year), value: y.amount }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{agency.agency_name}</h1>
        {agency.agency_code && (
          <p className="text-sm text-muted-foreground font-mono mt-0.5">{agency.agency_code}</p>
        )}
      </div>

      {/* KPIs */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          <KpiCard title="Total Awards" value={stats.total_awards.toLocaleString()} />
          <KpiCard title="Total Obligated" value={formatUSD(stats.total_obligated_amount)} />
          {hhiScore !== null && (
            <KpiCard
              title="Vendor Concentration (HHI)"
              value={hhiScore.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            />
          )}
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Spending Over Time */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Spending Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={period} onValueChange={(v) => setPeriod(v as typeof period)}>
              <TabsList className="mb-4">
                <TabsTrigger value="month">Monthly</TabsTrigger>
                <TabsTrigger value="quarter">Quarterly</TabsTrigger>
                <TabsTrigger value="year">Yearly</TabsTrigger>
              </TabsList>
              <TabsContent value={period}>
                {sLoading && <p className="text-muted-foreground">Loading…</p>}
                {spending && <SpendingChart data={spending} />}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Spending by Year */}
        {spendByYear.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Annual Spend</CardTitle>
              <p className="text-xs text-muted-foreground">Total obligated by fiscal year</p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={spendByYear} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'currentColor' }} />
                  <YAxis tickFormatter={formatUSD} tick={{ fontSize: 11, fill: 'currentColor' }} width={72} />
                  <Tooltip
                    formatter={(v) => [formatUSD(v as number), 'Obligated']}
                    contentStyle={{
                      background: 'var(--popover)',
                      border: '1px solid var(--border)',
                      color: 'var(--popover-foreground)',
                      borderRadius: '6px',
                    }}
                  />
                  <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Top Vendors */}
      {topVendors.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Top Vendors</CardTitle>
            <p className="text-xs text-muted-foreground">Highest-value contractors for this agency</p>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead className="text-right">Awards</TableHead>
                  <TableHead className="text-right">Total Obligated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topVendors.map((v) => (
                  <TableRow key={v.canonical_name}>
                    <TableCell className="font-medium">{v.canonical_name}</TableCell>
                    <TableCell className="text-right">{v.count.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{formatUSD(v.amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function AgencyDetailPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
      <AgencyDetail />
    </Suspense>
  );
}
