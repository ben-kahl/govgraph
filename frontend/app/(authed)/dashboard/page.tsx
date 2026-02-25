'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { MarketShareChart } from '@/components/MarketShareChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['marketShare'],
    queryFn: () => api.analytics.marketShare(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <Card>
        <CardHeader>
          <CardTitle>Top Vendors by Contract Value</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-muted-foreground">Loading…</p>}
          {isError && <p className="text-destructive">Failed to load market share data.</p>}
          {data && <MarketShareChart data={data} />}
        </CardContent>
      </Card>
    </div>
  );
}
