'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { PaginatedVendors, PaginatedAgencies } from '@/types/api';

type Mode = 'vendor' | 'agency';

const NODE_COLORS: Record<string, string> = {
  Vendor: '#ef4444',
  Agency: '#22c55e',
  Contract: '#f59e0b',
};

export default function GraphPage() {
  const [mode, setMode] = useState<Mode>('vendor');
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeEntity, setActiveEntity] = useState<{ id: string; name: string; type: Mode } | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ id: string; label: string; type: string } | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(t);
  }, [searchText]);

  const { data: suggestions } = useQuery({
    queryKey: ['graph-search', mode, debouncedSearch],
    queryFn: async () => {
      if (mode === 'vendor') {
        const result = await api.vendors.list(debouncedSearch, 1, 8);
        return result.items.map((v) => ({ id: v.id, name: v.canonical_name }));
      }
      const result = await api.agencies.list(debouncedSearch, 1, 8);
      return result.items.map((a) => ({ id: a.id, name: a.agency_name }));
    },
    enabled: debouncedSearch.length >= 2,
  });

  const { data: graphData, isLoading, isError } = useQuery({
    queryKey: ['graph', activeEntity?.type, activeEntity?.id],
    queryFn: () => {
      if (!activeEntity) throw new Error('No entity selected');
      return activeEntity.type === 'vendor'
        ? api.graph.vendor(activeEntity.id)
        : api.graph.agency(activeEntity.id);
    },
    enabled: !!activeEntity,
  });

  function selectEntity(id: string, name: string) {
    setActiveEntity({ id, name, type: mode });
    setSearchText(name);
    setShowDropdown(false);
    setSelectedNode(null);
  }

  function switchMode(newMode: Mode) {
    setMode(newMode);
    setSearchText('');
    setDebouncedSearch('');
    setShowDropdown(false);
  }

  const legendCounts = graphData?.nodes.reduce<Record<string, number>>((acc, n) => {
    const t = n.data.type;
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {}) ?? {};

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Sidebar */}
      <div className="w-72 flex flex-col gap-4 shrink-0">
        <h1 className="text-2xl font-bold">Graph Explorer</h1>

        {/* Type toggle */}
        <div className="flex gap-2">
          <Button
            variant={mode === 'vendor' ? 'default' : 'outline'}
            size="sm"
            onClick={() => switchMode('vendor')}
          >
            Vendor
          </Button>
          <Button
            variant={mode === 'agency' ? 'default' : 'outline'}
            size="sm"
            onClick={() => switchMode('agency')}
          >
            Agency
          </Button>
        </div>

        {/* Search with dropdown */}
        <div className="relative">
          <Input
            placeholder={mode === 'vendor' ? 'Search vendors…' : 'Search agencies…'}
            value={searchText}
            onChange={(e) => {
              setSearchText(e.target.value);
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
          />
          {showDropdown && suggestions && suggestions.length > 0 && (
            <ul className="absolute z-10 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-60 overflow-auto">
              {suggestions.map((item) => (
                <li
                  key={item.id}
                  className="px-3 py-2 text-sm cursor-pointer hover:bg-accent"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => selectEntity(item.id, item.name)}
                >
                  {item.name}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Legend */}
        {graphData && graphData.nodes.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">Legend</p>
            {Object.entries(legendCounts).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2 text-sm">
                <span
                  className="inline-block w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLORS[type] ?? '#94a3b8' }}
                />
                <span className="flex-1">{type}</span>
                <span className="text-muted-foreground">{count}</span>
              </div>
            ))}
          </div>
        )}

        {/* Selected node panel */}
        {selectedNode && (
          <div className="rounded-lg border p-3 space-y-2">
            <p className="text-sm font-medium truncate">{selectedNode.label}</p>
            <span
              className="inline-block px-2 py-0.5 rounded text-xs text-white"
              style={{ backgroundColor: NODE_COLORS[selectedNode.type] ?? '#94a3b8' }}
            >
              {selectedNode.type}
            </span>
            {(selectedNode.type === 'Vendor' || selectedNode.type === 'Agency') && (
              <div className="pt-1">
                <Link
                  href={`/${selectedNode.type.toLowerCase()}s/detail?id=${selectedNode.id}`}
                  className="text-xs text-primary hover:underline"
                >
                  View detail →
                </Link>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 border rounded-lg overflow-hidden bg-muted/20">
        {!activeEntity && (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
            Search for a vendor or agency to explore the graph.
          </div>
        )}
        {activeEntity && isLoading && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Loading graph…
          </div>
        )}
        {activeEntity && isError && (
          <div className="flex h-full items-center justify-center text-destructive">
            Failed to load graph.
          </div>
        )}
        {graphData && graphData.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            No nodes found.
          </div>
        )}
        {graphData && graphData.nodes.length > 0 && (
          <CytoscapeGraph
            nodes={graphData.nodes}
            edges={graphData.edges}
            highlightedId={activeEntity?.id}
            onNodeClick={setSelectedNode}
          />
        )}
      </div>
    </div>
  );
}
