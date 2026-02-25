'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function formatDollars(v: number) {
  return `$${(v / 1_000_000).toFixed(2)}M`;
}

export default function RiskPage() {
  const { data: spikes, isLoading: spikesLoading } = useQuery({
    queryKey: ['awardSpikes'],
    queryFn: () => api.analytics.awardSpikes(),
  });

  const { data: entrants, isLoading: entrantsLoading } = useQuery({
    queryKey: ['newEntrants'],
    queryFn: () => api.analytics.newEntrants(),
  });

  const { data: soleSource, isLoading: ssLoading } = useQuery({
    queryKey: ['soleSource'],
    queryFn: () => api.analytics.soleSource(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Risk Indicators</h1>

      <Card>
        <CardHeader>
          <CardTitle>Award Spikes</CardTitle>
        </CardHeader>
        <CardContent>
          {spikesLoading && <p className="text-muted-foreground">Loading…</p>}
          {spikes && spikes.length === 0 && <p className="text-muted-foreground">No anomalies detected.</p>}
          {spikes && spikes.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Contract ID</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Avg Amount</TableHead>
                  <TableHead>Z-Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {spikes.map((s, i) => (
                  <TableRow key={i}>
                    <TableCell>{s.canonical_name}</TableCell>
                    <TableCell className="font-mono text-xs">{s.contract_id}</TableCell>
                    <TableCell>{formatDollars(s.obligated_amount)}</TableCell>
                    <TableCell>{formatDollars(s.avg_amount)}</TableCell>
                    <TableCell className="font-mono">{s.z_score.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>New Entrants (last 90 days)</CardTitle>
        </CardHeader>
        <CardContent>
          {entrantsLoading && <p className="text-muted-foreground">Loading…</p>}
          {entrants && entrants.length === 0 && <p className="text-muted-foreground">No new entrants.</p>}
          {entrants && entrants.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead>First Award</TableHead>
                  <TableHead>Awards</TableHead>
                  <TableHead>Total Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entrants.map((e, i) => (
                  <TableRow key={i}>
                    <TableCell>{e.canonical_name}</TableCell>
                    <TableCell>{e.first_award}</TableCell>
                    <TableCell>{e.award_count}</TableCell>
                    <TableCell>{formatDollars(e.total_value)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sole-Source Agencies</CardTitle>
        </CardHeader>
        <CardContent>
          {ssLoading && <p className="text-muted-foreground">Loading…</p>}
          {soleSource && soleSource.length === 0 && <p className="text-muted-foreground">No sole-source agencies.</p>}
          {soleSource && soleSource.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agency</TableHead>
                  <TableHead>Sole Vendor</TableHead>
                  <TableHead>Contracts</TableHead>
                  <TableHead>Total Spend</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {soleSource.map((s, i) => (
                  <TableRow key={i}>
                    <TableCell>{s.agency_name}</TableCell>
                    <TableCell>{s.sole_vendor}</TableCell>
                    <TableCell>{s.contracts}</TableCell>
                    <TableCell>{formatDollars(s.total_spend)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
