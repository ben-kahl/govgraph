'use client';
import { use, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { SpendingChart } from '@/components/SpendingChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function AgencyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [period, setPeriod] = useState<'month' | 'quarter' | 'year'>('month');

  const { data: agency, isLoading: aLoading } = useQuery({
    queryKey: ['agency', id],
    queryFn: () => api.agencies.getById(id),
  });

  const { data: spending, isLoading: sLoading } = useQuery({
    queryKey: ['agencySpending', id, period],
    queryFn: () => api.analytics.spendingOverTime(id, period),
  });

  if (aLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!agency) return <p className="text-destructive">Agency not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{agency.name}</h1>
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
