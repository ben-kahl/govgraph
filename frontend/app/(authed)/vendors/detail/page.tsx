'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '@/lib/api';
import { formatUSD } from '@/lib/utils';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import { SpendingChart } from '@/components/SpendingChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

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

function VendorDetail() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') ?? '';

  const { data: vendor, isLoading: vLoading } = useQuery({
    queryKey: ['vendor', id],
    queryFn: () => api.vendors.getById(id),
    enabled: !!id,
  });

  const { data: awardTypes } = useQuery({
    queryKey: ['vendorAwardTypes', id],
    queryFn: () => api.vendors.awardTypes(id),
    enabled: !!id,
  });

  const { data: velocity } = useQuery({
    queryKey: ['vendorVelocity', id],
    queryFn: () => api.vendors.velocity(id),
    enabled: !!id,
  });

  const { data: graph, isLoading: gLoading } = useQuery({
    queryKey: ['vendorGraph', id],
    queryFn: () => api.graph.vendor(id),
    enabled: !!id,
  });

  if (vLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!vendor) return <p className="text-destructive">Vendor not found.</p>;

  const totalContracts = awardTypes?.reduce((s, t) => s + t.count, 0) ?? 0;
  const totalObligated = awardTypes?.reduce((s, t) => s + t.total_value, 0) ?? 0;
  const avgAward = totalContracts > 0 ? totalObligated / totalContracts : 0;

  const velocityData = velocity?.map((v) => ({
    period: v.quarter.slice(0, 7),
    total_obligated: v.total,
    contract_count: v.awards,
  })) ?? [];

  const typeChartData = (awardTypes ?? [])
    .filter((t) => t.total_value > 0)
    .sort((a, b) => b.total_value - a.total_value)
    .map((t) => ({ name: t.award_type ?? 'Unknown', value: t.total_value, count: t.count }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{vendor.canonical_name}</h1>
        <div className="flex gap-3 mt-1 text-sm text-muted-foreground">
          {vendor.uei && <span>UEI: <span className="font-mono">{vendor.uei}</span></span>}
          {vendor.duns && <span>DUNS: <span className="font-mono">{vendor.duns}</span></span>}
        </div>
      </div>

      {/* KPIs */}
      {awardTypes && (
        <div className="grid grid-cols-3 gap-4">
          <KpiCard title="Total Contracts" value={totalContracts.toLocaleString()} />
          <KpiCard title="Total Obligated" value={formatUSD(totalObligated)} />
          <KpiCard title="Avg Award Size" value={formatUSD(avgAward)} />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {velocityData.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Award Velocity</CardTitle>
              <p className="text-xs text-muted-foreground">Quarterly contract spend</p>
            </CardHeader>
            <CardContent>
              <SpendingChart data={velocityData} />
            </CardContent>
          </Card>
        )}

        {typeChartData.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Award Type Breakdown</CardTitle>
              <p className="text-xs text-muted-foreground">Total obligated by contract type</p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  layout="vertical"
                  data={typeChartData}
                  margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={formatUSD} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" width={28} tick={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(v: number) => [formatUSD(v), 'Total Obligated']}
                    labelFormatter={(l) => `Type: ${l}`}
                  />
                  <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Graph */}
      <Card>
        <CardHeader>
          <CardTitle>Relationship Graph</CardTitle>
          <p className="text-xs text-muted-foreground">Top contracts by value and connected agencies</p>
        </CardHeader>
        <CardContent style={{ height: 500 }}>
          {gLoading && <p className="text-muted-foreground">Loading graph…</p>}
          {graph && <CytoscapeGraph nodes={graph.nodes} edges={graph.edges} />}
        </CardContent>
      </Card>
    </div>
  );
}

export default function VendorDetailPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
      <VendorDetail />
    </Suspense>
  );
}
