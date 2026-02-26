'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type Mode = 'vendor' | 'agency';

export default function GraphPage() {
  const [mode, setMode] = useState<Mode>('vendor');
  const [entityId, setEntityId] = useState('');
  const [activeId, setActiveId] = useState('');
  const [activeMode, setActiveMode] = useState<Mode>('vendor');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['graph', activeMode, activeId],
    queryFn: () => {
      if (activeMode === 'vendor') return api.graph.vendor(activeId);
      return api.graph.agency(activeId);
    },
    enabled: !!activeId,
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
          <option value="vendor">Vendor by ID</option>
          <option value="agency">Agency by ID</option>
        </select>
        <Input
          placeholder="Entity ID…"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="max-w-xs"
        />
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
