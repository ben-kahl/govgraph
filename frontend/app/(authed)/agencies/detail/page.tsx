'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { SpendingChart } from '@/components/SpendingChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

function AgencyDetail() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') ?? '';
  const [period, setPeriod] = useState<'month' | 'quarter' | 'year'>('month');

  const { data: agency, isLoading: aLoading } = useQuery({
    queryKey: ['agency', id],
    queryFn: () => api.agencies.getById(id),
    enabled: !!id,
  });

  const { data: spending, isLoading: sLoading } = useQuery({
    queryKey: ['agencySpending', id, period],
    queryFn: () => api.analytics.spendingOverTime(id, period),
    enabled: !!id,
  });

  if (aLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!agency) return <p className="text-destructive">Agency not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{agency.agency_name}</h1>
        {agency.agency_code && (
          <p className="text-sm text-muted-foreground font-mono">{agency.agency_code}</p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Spending Over Time</CardTitle>
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
