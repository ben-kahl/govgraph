'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type Mode = 'hubs' | 'vendor' | 'agency';

export default function GraphPage() {
  const [mode, setMode] = useState<Mode>('hubs');
  const [entityId, setEntityId] = useState('');
  const [activeId, setActiveId] = useState('');
  const [activeMode, setActiveMode] = useState<Mode>('hubs');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['graph', activeMode, activeId],
    queryFn: () => {
      if (activeMode === 'hubs') return api.graph.hubs();
      if (activeMode === 'vendor') return api.graph.vendor(activeId);
      return api.graph.agency(activeId);
    },
    enabled: activeMode === 'hubs' || !!activeId,
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setActiveId(entityId);
    setActiveMode(mode);
  }

  return (
    <div className="space-y-4 h-[calc(100vh-120px)] flex flex-col">
      <h1 className="text-2xl font-bold">Graph Explorer</h1>

      <form onSubmit={handleSearch} className="flex gap-2 flex-wrap">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as Mode)}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="hubs">Hub Vendors</option>
          <option value="vendor">Vendor by ID</option>
          <option value="agency">Agency by ID</option>
        </select>
        {mode !== 'hubs' && (
          <Input
            placeholder="Entity ID…"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            className="max-w-xs"
          />
        )}
        <Button type="submit">Load</Button>
      </form>

      <div className="flex-1 border rounded-lg overflow-hidden bg-muted/20">
        {isLoading && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Loading graph…
          </div>
        )}
        {isError && (
          <div className="flex h-full items-center justify-center text-destructive">
            Failed to load graph.
          </div>
        )}
        {data && data.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            No nodes found.
          </div>
        )}
        {data && data.nodes.length > 0 && (
          <CytoscapeGraph nodes={data.nodes} edges={data.edges} />
        )}
      </div>
    </div>
  );
}
