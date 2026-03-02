'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { formatUSD } from '@/lib/utils';
import { MarketShareChart } from '@/components/MarketShareChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

function KpiCard({ title, value, isLoading }: { title: string; value: string; isLoading: boolean }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-2xl font-bold text-muted-foreground animate-pulse">—</p>
        ) : (
          <p className="text-2xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['summary'],
    queryFn: () => api.analytics.summary(),
  });

  const { data: marketShare, isLoading: marketShareLoading, isError: marketShareError } = useQuery({
    queryKey: ['marketShare'],
    queryFn: () => api.analytics.marketShare(),
  });

  const { data: agencyShare, isLoading: agencyShareLoading, isError: agencyShareError } = useQuery({
    queryKey: ['agencyMarketShare'],
    queryFn: () => api.analytics.agencyMarketShare(),
  });

  const { data: vendorResults } = useQuery({
    queryKey: ['dashSearch', 'vendors', query],
    queryFn: () => api.vendors.list(query, 1, 5),
    enabled: query.length > 0,
  });

  const { data: agencyResults } = useQuery({
    queryKey: ['dashSearch', 'agencies', query],
    queryFn: () => api.agencies.list(query, 1, 5),
    enabled: query.length > 0,
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(search);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Combined search */}
      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <Input
          placeholder="Search vendors or agencies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button type="submit">Search</Button>
      </form>

      {query && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Vendors</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {!vendorResults?.items.length && (
                <p className="text-sm text-muted-foreground">No vendors found.</p>
              )}
              {vendorResults?.items.map((v) => (
                <div key={v.id}>
                  <Link href={`/vendors/detail?id=${v.id}`} className="text-sm text-blue-600 hover:underline">
                    {v.canonical_name}
                  </Link>
                </div>
              ))}
              {vendorResults && vendorResults.total > 5 && (
                <Link href={`/vendors?q=${encodeURIComponent(query)}`} className="text-xs text-muted-foreground hover:underline">
                  View all {vendorResults.total.toLocaleString()} results →
                </Link>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Agencies</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {!agencyResults?.items.length && (
                <p className="text-sm text-muted-foreground">No agencies found.</p>
              )}
              {agencyResults?.items.map((a) => (
                <div key={a.id}>
                  <Link href={`/agencies/detail?id=${a.id}`} className="text-sm text-blue-600 hover:underline">
                    {a.agency_name}
                  </Link>
                </div>
              ))}
              {agencyResults && agencyResults.total > 5 && (
                <Link href={`/agencies?q=${encodeURIComponent(query)}`} className="text-xs text-muted-foreground hover:underline">
                  View all {agencyResults.total.toLocaleString()} results →
                </Link>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          title="Total Contracts"
          value={summary ? summary.total_contracts.toLocaleString() : '—'}
          isLoading={summaryLoading}
        />
        <KpiCard
          title="Total Vendors"
          value={summary ? summary.total_vendors.toLocaleString() : '—'}
          isLoading={summaryLoading}
        />
        <KpiCard
          title="Total Obligated"
          value={summary ? formatUSD(summary.total_obligated_amount) : '—'}
          isLoading={summaryLoading}
        />
        <KpiCard
          title="Agencies"
          value={summary ? summary.total_agencies.toLocaleString() : '—'}
          isLoading={summaryLoading}
        />
      </div>

      {/* Vendor market share chart */}
      <Card>
        <CardHeader>
          <CardTitle>Top Vendors by Contract Value</CardTitle>
        </CardHeader>
        <CardContent>
          {marketShareLoading && <p className="text-muted-foreground">Loading…</p>}
          {marketShareError && <p className="text-destructive">Failed to load market share data.</p>}
          {marketShare && <MarketShareChart data={marketShare} />}
        </CardContent>
      </Card>

      {/* Agency award volume chart */}
      <Card>
        <CardHeader>
          <CardTitle>Top Agencies by Award Volume</CardTitle>
        </CardHeader>
        <CardContent>
          {agencyShareLoading && <p className="text-muted-foreground">Loading…</p>}
          {agencyShareError && <p className="text-destructive">Failed to load agency data.</p>}
          {agencyShare && <MarketShareChart data={agencyShare} nameKey="agency_name" />}
        </CardContent>
      </Card>
    </div>
  );
}
