'use client';
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import type { ClickedNode } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { GraphResponse } from '@/types/api';

type Mode = 'vendor' | 'agency';

const NODE_COLORS: Record<string, string> = {
  Vendor: '#ef4444',
  Agency: '#22c55e',
  Contract: '#f59e0b',
};

const LAYOUTS = [
  { value: 'cose', label: 'CoSE (force-directed)' },
  { value: 'circle', label: 'Circle' },
  { value: 'grid', label: 'Grid' },
  { value: 'breadthfirst', label: 'Breadth-first' },
  { value: 'concentric', label: 'Concentric' },
];

function formatUSD(amount: number): string {
  if (amount >= 1e9) return `$${(amount / 1e9).toFixed(1)}B`;
  if (amount >= 1e6) return `$${(amount / 1e6).toFixed(1)}M`;
  if (amount >= 1e3) return `$${(amount / 1e3).toFixed(0)}K`;
  return `$${amount.toFixed(0)}`;
}

function getContractRelated(nodeId: string, graphData: GraphResponse) {
  const nodeMap = new Map(graphData.nodes.map((n) => [n.data.id, n.data.label]));
  const vendorEdge = graphData.edges.find(
    (e) => e.data.label === 'AWARDED' && e.data.target === nodeId
  );
  const awardingEdge = graphData.edges.find(
    (e) => e.data.label === 'AWARDED_CONTRACT' && e.data.target === nodeId
  );
  const fundingEdge = graphData.edges.find(
    (e) => e.data.label === 'FUNDED' && e.data.target === nodeId
  );
  return {
    vendor: vendorEdge ? nodeMap.get(vendorEdge.data.source) : undefined,
    awardingAgency: awardingEdge ? nodeMap.get(awardingEdge.data.source) : undefined,
    fundingAgency: fundingEdge ? nodeMap.get(fundingEdge.data.source) : undefined,
  };
}

export default function GraphPage() {
  const [mode, setMode] = useState<Mode>('vendor');
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeEntity, setActiveEntity] = useState<{ id: string; name: string; type: Mode } | null>(null);
  const [selectedNode, setSelectedNode] = useState<ClickedNode | null>(null);
  const [layoutName, setLayoutName] = useState('cose');

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

  const contractRelated =
    selectedNode?.type === 'Contract' && graphData
      ? getContractRelated(selectedNode.id, graphData)
      : null;

  return (
    <div className="flex gap-4 h-[calc(100vh-120px)]">
      {/* Sidebar */}
      <div className="w-72 flex flex-col gap-4 shrink-0 overflow-y-auto">
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

        {/* Layout selector */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Layout</label>
          <select
            value={layoutName}
            onChange={(e) => setLayoutName(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm bg-background"
          >
            {LAYOUTS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
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
            <p className="text-sm font-medium leading-snug">{selectedNode.label}</p>
            <span
              className="inline-block px-2 py-0.5 rounded text-xs text-white"
              style={{ backgroundColor: NODE_COLORS[selectedNode.type] ?? '#94a3b8' }}
            >
              {selectedNode.type}
            </span>

            {selectedNode.type === 'Contract' && (
              <div className="space-y-1.5 pt-1 text-xs text-muted-foreground">
                {!!selectedNode.properties?.description && (
                  <p className="text-foreground leading-snug">
                    {String(selectedNode.properties.description)}
                  </p>
                )}
                {!!selectedNode.properties?.contractId && (
                  <p>
                    <span className="font-medium">ID:</span>{' '}
                    <span className="font-mono">{String(selectedNode.properties.contractId)}</span>
                  </p>
                )}
                {selectedNode.properties?.obligatedAmount != null && (
                  <p>
                    <span className="font-medium">Amount:</span>{' '}
                    {formatUSD(Number(selectedNode.properties.obligatedAmount))}
                  </p>
                )}
                {!!selectedNode.properties?.signedDate && (
                  <p>
                    <span className="font-medium">Signed:</span>{' '}
                    {String(selectedNode.properties.signedDate)}
                  </p>
                )}
                {contractRelated?.vendor && (
                  <p>
                    <span className="font-medium">Vendor:</span> {contractRelated.vendor}
                  </p>
                )}
                {contractRelated?.awardingAgency && (
                  <p>
                    <span className="font-medium">Awarding Agency:</span>{' '}
                    {contractRelated.awardingAgency}
                  </p>
                )}
                {contractRelated?.fundingAgency && (
                  <p>
                    <span className="font-medium">Funding Agency:</span>{' '}
                    {contractRelated.fundingAgency}
                  </p>
                )}
              </div>
            )}

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
            layoutName={layoutName}
          />
        )}
      </div>
    </div>
  );
}
