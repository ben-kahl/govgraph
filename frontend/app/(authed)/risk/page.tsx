'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatUSD } from '@/lib/utils';

const PAGE_SIZE = 10;

function PaginationControls({
  page,
  total,
  onPrev,
  onNext,
}: {
  page: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center gap-2 pt-2">
      <Button variant="outline" size="sm" disabled={page === 0} onClick={onPrev}>
        Previous
      </Button>
      <span className="text-sm text-muted-foreground">
        Page {page + 1} of {totalPages}
      </span>
      <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={onNext}>
        Next
      </Button>
    </div>
  );
}

export default function RiskPage() {
  const [spikesPage, setSpikesPage] = useState(0);
  const [entrantsPage, setEntrantsPage] = useState(0);
  const [ssPage, setSsPage] = useState(0);
  const [circularPage, setCircularPage] = useState(0);

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

  const { data: circular, isLoading: circularLoading } = useQuery({
    queryKey: ['circularSubcontracts'],
    queryFn: () => api.analytics.circularSubcontracts(),
  });

  const spikesSlice = spikes?.slice(spikesPage * PAGE_SIZE, (spikesPage + 1) * PAGE_SIZE) ?? [];
  const entrantsSlice = entrants?.slice(entrantsPage * PAGE_SIZE, (entrantsPage + 1) * PAGE_SIZE) ?? [];
  const ssSlice = soleSource?.slice(ssPage * PAGE_SIZE, (ssPage + 1) * PAGE_SIZE) ?? [];
  const circularSlice = circular?.slice(circularPage * PAGE_SIZE, (circularPage + 1) * PAGE_SIZE) ?? [];

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
            <>
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
                  {spikesSlice.map((s, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Link
                          href={`/vendors/detail?id=${s.vendor_id}`}
                          className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                        >
                          {s.canonical_name}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{s.contract_id}</TableCell>
                      <TableCell>{formatUSD(s.obligated_amount)}</TableCell>
                      <TableCell>{formatUSD(s.avg_amount)}</TableCell>
                      <TableCell className="font-mono">{s.z_score.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <PaginationControls
                page={spikesPage}
                total={spikes.length}
                onPrev={() => setSpikesPage((p) => p - 1)}
                onNext={() => setSpikesPage((p) => p + 1)}
              />
            </>
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
            <>
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
                  {entrantsSlice.map((e, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Link
                          href={`/vendors/detail?id=${e.vendor_id}`}
                          className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                        >
                          {e.canonical_name}
                        </Link>
                      </TableCell>
                      <TableCell>{e.first_award}</TableCell>
                      <TableCell>{e.award_count}</TableCell>
                      <TableCell>{formatUSD(e.total_value)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <PaginationControls
                page={entrantsPage}
                total={entrants.length}
                onPrev={() => setEntrantsPage((p) => p - 1)}
                onNext={() => setEntrantsPage((p) => p + 1)}
              />
            </>
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
            <>
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
                  {ssSlice.map((s, i) => (
                    <TableRow key={i}>
                      <TableCell>{s.agency_name}</TableCell>
                      <TableCell>
                        <Link
                          href={`/vendors?q=${encodeURIComponent(s.sole_vendor)}`}
                          className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                        >
                          {s.sole_vendor}
                        </Link>
                      </TableCell>
                      <TableCell>{s.contracts}</TableCell>
                      <TableCell>{formatUSD(s.total_spend)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <PaginationControls
                page={ssPage}
                total={soleSource.length}
                onPrev={() => setSsPage((p) => p - 1)}
                onNext={() => setSsPage((p) => p + 1)}
              />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Circular Subcontracting Chains</CardTitle>
        </CardHeader>
        <CardContent>
          {circularLoading && <p className="text-muted-foreground">Loading…</p>}
          {circular && circular.length === 0 && <p className="text-muted-foreground">No circular chains detected.</p>}
          {circular && circular.length > 0 && (
            <>
              <div className="space-y-3">
                {circularSlice.map((chain, i) => (
                  <div key={i} className="rounded-md border p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="destructive" className="text-xs">
                        Loop · {chain.loop_length} hop{chain.loop_length !== 1 ? 's' : ''}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-1 text-sm">
                      {chain.loop_members.map((member, j) => (
                        <span key={j} className="flex items-center gap-1">
                          <Link
                            href={`/vendors/detail?id=${member.id}`}
                            className="text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                          >
                            {member.name}
                          </Link>
                          {j < chain.loop_members.length - 1 && (
                            <span className="text-muted-foreground">→</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <PaginationControls
                page={circularPage}
                total={circular.length}
                onPrev={() => setCircularPage((p) => p - 1)}
                onNext={() => setCircularPage((p) => p + 1)}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
