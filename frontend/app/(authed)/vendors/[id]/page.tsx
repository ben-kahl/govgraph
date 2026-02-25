'use client';
import { use } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function VendorDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const { data: vendor, isLoading: vLoading } = useQuery({
    queryKey: ['vendor', id],
    queryFn: () => api.vendors.getById(id),
  });

  const { data: graph, isLoading: gLoading } = useQuery({
    queryKey: ['vendorGraph', id],
    queryFn: () => api.graph.vendor(id),
  });

  if (vLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (!vendor) return <p className="text-destructive">Vendor not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{vendor.canonical_name}</h1>
        <div className="flex gap-2 mt-1 text-sm text-muted-foreground">
          {vendor.uei && <span>UEI: <span className="font-mono">{vendor.uei}</span></span>}
          {vendor.duns && <span>DUNS: <span className="font-mono">{vendor.duns}</span></span>}
          <span>Confidence: {(vendor.resolution_confidence * 100).toFixed(0)}%</span>
          {vendor.resolved_by_llm && <Badge variant="secondary">LLM Resolved</Badge>}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Relationship Graph</CardTitle>
        </CardHeader>
        <CardContent style={{ height: 500 }}>
          {gLoading && <p className="text-muted-foreground">Loading graph…</p>}
          {graph && <CytoscapeGraph nodes={graph.nodes} edges={graph.edges} />}
        </CardContent>
      </Card>
    </div>
  );
}
