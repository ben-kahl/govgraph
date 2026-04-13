'use client';
import { Suspense, useState, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '@/lib/api';
import { formatUSD } from '@/lib/utils';
import Link from 'next/link';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import type { ClickedNode } from '@/components/CytoscapeGraph';
import { SpendingChart } from '@/components/SpendingChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import type { GraphNode, GraphEdge, GraphResponse } from '@/types/api';

function mergeGraphResponses(responses: GraphResponse[]): GraphResponse {
  const seenNodes = new Set<string>();
  const seenEdges = new Set<string>();
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  for (const r of responses) {
    for (const n of r.nodes) {
      if (!seenNodes.has(n.data.id)) { seenNodes.add(n.data.id); nodes.push(n); }
    }
    for (const e of r.edges) {
      if (!seenEdges.has(e.data.id)) { seenEdges.add(e.data.id); edges.push(e); }
    }
  }
  return { nodes, edges };
}

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
  const [expansions, setExpansions] = useState<Map<string, GraphResponse>>(() => new Map());
  const [expansionRootId, setExpansionRootId] = useState<string | null>(null);

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

  const { data: vendorStats } = useQuery({
    queryKey: ['vendorStats', id],
    queryFn: () => api.vendors.stats(id),
    enabled: !!id,
  });

  const { data: graph, isLoading: gLoading } = useQuery({
    queryKey: ['vendorGraph', id],
    queryFn: () => api.graph.vendor(id),
    enabled: !!id,
  });

  const allGraphData = useMemo(() => {
    if (!graph) return undefined;
    if (expansions.size === 0) return graph;
    return mergeGraphResponses([graph, ...expansions.values()]);
  }, [graph, expansions]);

  async function expandNode(node: ClickedNode) {
    if (expansions.has(node.id)) {
      setExpansionRootId(null);
      setExpansions((prev) => { const next = new Map(prev); next.delete(node.id); return next; });
      return;
    }
    try {
      let result: GraphResponse;
      if (node.type === 'Vendor') result = await api.graph.vendor(node.id);
      else if (node.type === 'Agency') result = await api.graph.agency(node.id);
      else result = await api.graph.contract(node.id);
      setExpansionRootId(node.id);
      setExpansions((prev) => new Map(prev).set(node.id, result));
    } catch { /* fail silently */ }
  }

  if (vLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!vendor) return <p className="text-destructive">Vendor not found.</p>;

  const totalContracts = awardTypes?.reduce((s, t) => s + t.count, 0) ?? 0;
  const totalObligated = awardTypes?.reduce((s, t) => s + Number(t.total_value), 0) ?? 0;
  const avgAward = totalContracts > 0 ? totalObligated / totalContracts : 0;

  const velocityData = velocity?.map((v) => ({
    period: v.quarter.slice(0, 7),
    total_obligated: Number(v.total),
    contract_count: v.awards,
  })) ?? [];

  const typeChartData = (awardTypes ?? [])
    .filter((t) => Number(t.total_value) > 0)
    .sort((a, b) => Number(b.total_value) - Number(a.total_value))
    .map((t) => ({ name: t.award_type ?? 'Unknown', value: Number(t.total_value), count: t.count }));

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
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                  <XAxis type="number" tickFormatter={formatUSD} tick={{ fontSize: 11, fill: 'currentColor' }} />
                  <YAxis type="category" dataKey="name" width={28} tick={{ fontSize: 12, fill: 'currentColor' }} />
                  <Tooltip
                    formatter={(v) => [formatUSD(v as number), 'Total Obligated']}
                    labelFormatter={(l) => `Type: ${l}`}
                    contentStyle={{
                      background: 'var(--popover)',
                      border: '1px solid var(--border)',
                      color: 'var(--popover-foreground)',
                      borderRadius: '6px',
                    }}
                  />
                  <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Top Agencies */}
      {vendorStats && vendorStats.top_agencies.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Top Agencies</CardTitle>
            <p className="text-xs text-muted-foreground">Highest-value agencies by contract spend with this vendor</p>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agency</TableHead>
                  <TableHead className="text-right">Awards</TableHead>
                  <TableHead className="text-right">Total Obligated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vendorStats.top_agencies.map((a) => (
                  <TableRow key={a.agency_id}>
                    <TableCell className="font-medium">
                      <Link href={`/agencies/detail?id=${a.agency_id}`} className="text-primary hover:underline">
                        {a.agency_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right">{a.count.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{formatUSD(Number(a.amount))}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Graph */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Relationship Graph</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">Top contracts by value and connected agencies</p>
            </div>
            {expansions.size > 0 && (
              <button
                className="text-xs text-muted-foreground hover:text-destructive shrink-0"
                onClick={() => { setExpansions(new Map()); setExpansionRootId(null); }}
              >
                Clear expansions ({expansions.size})
              </button>
            )}
          </div>
          {graph && (
            <p className="text-xs text-muted-foreground italic">
              Double-click any node to expand its connections · double-click again to collapse
            </p>
          )}
        </CardHeader>
        <CardContent style={{ height: 500 }}>
          {gLoading && <p className="text-muted-foreground">Loading graph…</p>}
          {allGraphData && allGraphData.nodes.length > 0 && (
            <CytoscapeGraph
              nodes={allGraphData.nodes}
              edges={allGraphData.edges}
              expandedIds={[...expansions.keys()]}
              expansionRootId={expansionRootId}
              onNodeDoubleClick={expandNode}
            />
          )}
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
