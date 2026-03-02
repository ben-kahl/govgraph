'use client';
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import type { ClickedNode, LayoutOptions } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { GraphNode, GraphEdge, GraphResponse } from '@/types/api';

type Mode = 'vendor' | 'agency' | 'overview';
type EntityMode = 'vendor' | 'agency';

interface SelectedEntity {
  id: string;
  name: string;
  type: EntityMode;
}

const NODE_COLORS: Record<string, string> = {
  Vendor: '#ef4444',
  Agency: '#22c55e',
  Contract: '#f59e0b',
};

const LAYOUTS = [
  { value: 'fcose', label: 'fCOSE (fast force-directed)' },
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

function getContractRelated(nodeId: string, graphData: GraphResponse) {
  const nodeMap = new Map(graphData.nodes.map((n) => [n.data.id, n.data.label]));
  const vendorEdge = graphData.edges.find((e) => e.data.label === 'AWARDED' && e.data.target === nodeId);
  const awardingEdge = graphData.edges.find((e) => e.data.label === 'AWARDED_CONTRACT' && e.data.target === nodeId);
  const fundingEdge = graphData.edges.find((e) => e.data.label === 'FUNDED' && e.data.target === nodeId);
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
  const [selectedEntities, setSelectedEntities] = useState<SelectedEntity[]>([]);
  const [overviewActive, setOverviewActive] = useState(false);
  const [selectedNode, setSelectedNode] = useState<ClickedNode | null>(null);
  const [layoutName, setLayoutName] = useState('fcose');
  const [nodeRepulsion, setNodeRepulsion] = useState(4500);
  const [idealEdgeLength, setIdealEdgeLength] = useState(50);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(t);
  }, [searchText]);

  const { data: suggestions } = useQuery({
    queryKey: ['graph-search', mode, debouncedSearch],
    queryFn: async () => {
      if (mode === 'vendor') {
        const r = await api.vendors.list(debouncedSearch, 1, 8);
        return r.items.map((v) => ({ id: v.id, name: v.canonical_name }));
      }
      const r = await api.agencies.list(debouncedSearch, 1, 8);
      return r.items.map((a) => ({ id: a.id, name: a.agency_name }));
    },
    enabled: mode !== 'overview' && debouncedSearch.length >= 2,
  });

  const graphEnabled = overviewActive || selectedEntities.length > 0;
  const queryKey = overviewActive
    ? ['graph', 'overview']
    : ['graph', 'entities', selectedEntities.map((e) => `${e.type}:${e.id}`).join(',')];

  const { data: graphData, isLoading, isError } = useQuery({
    queryKey,
    queryFn: async () => {
      if (overviewActive) return api.graph.overview();
      const results = await Promise.all(
        selectedEntities.map((e) =>
          e.type === 'vendor' ? api.graph.vendor(e.id) : api.graph.agency(e.id)
        )
      );
      return mergeGraphResponses(results);
    },
    enabled: graphEnabled,
  });

  const highlightedIds = useMemo(
    () => (overviewActive ? [] : selectedEntities.map((e) => e.id)),
    [overviewActive, selectedEntities]
  );

  const layoutOptions = useMemo<LayoutOptions | undefined>(
    () =>
      layoutName === 'fcose' || layoutName === 'cose'
        ? { nodeRepulsion, idealEdgeLength }
        : undefined,
    [layoutName, nodeRepulsion, idealEdgeLength]
  );

  function addEntity(id: string, name: string) {
    if (selectedEntities.some((e) => e.id === id)) return;
    setSelectedEntities((prev) => [...prev, { id, name, type: mode as EntityMode }]);
    setSearchText('');
    setShowDropdown(false);
    setSelectedNode(null);
    if (overviewActive) setOverviewActive(false);
  }

  function removeEntity(id: string) {
    setSelectedEntities((prev) => prev.filter((e) => e.id !== id));
    setSelectedNode(null);
  }

  function switchMode(newMode: Mode) {
    setMode(newMode);
    setSearchText('');
    setDebouncedSearch('');
    setShowDropdown(false);
    if (newMode !== 'overview') setOverviewActive(false);
  }

  function loadOverview() {
    setOverviewActive(true);
    setSelectedEntities([]);
    setSelectedNode(null);
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
        <div className="flex gap-2 flex-wrap">
          <Button variant={mode === 'vendor' ? 'default' : 'outline'} size="sm" onClick={() => switchMode('vendor')}>
            Vendor
          </Button>
          <Button variant={mode === 'agency' ? 'default' : 'outline'} size="sm" onClick={() => switchMode('agency')}>
            Agency
          </Button>
          <Button variant={mode === 'overview' ? 'default' : 'outline'} size="sm" onClick={() => switchMode('overview')}>
            Overview
          </Button>
        </div>

        {/* Search or Load Overview */}
        {mode !== 'overview' ? (
          <div className="relative">
            <Input
              placeholder={mode === 'vendor' ? 'Search vendors…' : 'Search agencies…'}
              value={searchText}
              onChange={(e) => { setSearchText(e.target.value); setShowDropdown(true); }}
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
                    onClick={() => addEntity(item.id, item.name)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <Button className="w-full" onClick={loadOverview}>
            Load market overview
          </Button>
        )}

        {/* Selected entity chips */}
        {selectedEntities.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">Loaded ({selectedEntities.length})</p>
              <button
                className="text-xs text-muted-foreground hover:text-destructive"
                onClick={() => { setSelectedEntities([]); setSelectedNode(null); }}
              >
                Clear all
              </button>
            </div>
            {selectedEntities.map((e) => (
              <div key={e.id} className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: e.type === 'vendor' ? '#ef4444' : '#22c55e' }}
                />
                <span className="flex-1 truncate text-xs">{e.name}</span>
                <button
                  className="text-muted-foreground hover:text-destructive text-base leading-none"
                  onClick={() => removeEntity(e.id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Layout selector + options */}
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Layout</label>
            <select
              value={layoutName}
              onChange={(e) => setLayoutName(e.target.value)}
              className="w-full border rounded px-2 py-1 text-sm bg-background"
            >
              {LAYOUTS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {(layoutName === 'fcose' || layoutName === 'cose') && (
            <div className="space-y-2 pl-1">
              <div className="space-y-0.5">
                <div className="flex justify-between">
                  <label className="text-xs text-muted-foreground">Node Repulsion</label>
                  <span className="text-xs text-muted-foreground">{nodeRepulsion.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min={500}
                  max={50000}
                  step={500}
                  value={nodeRepulsion}
                  onChange={(e) => setNodeRepulsion(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              <div className="space-y-0.5">
                <div className="flex justify-between">
                  <label className="text-xs text-muted-foreground">Edge Length</label>
                  <span className="text-xs text-muted-foreground">{idealEdgeLength}</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={300}
                  step={5}
                  value={idealEdgeLength}
                  onChange={(e) => setIdealEdgeLength(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
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
            {graphData.edges.some((e) => e.data.label === 'SUBCONTRACTED') && (
              <div className="flex items-center gap-2 text-sm">
                <span className="inline-block w-6 h-0 border-t-2 border-dashed shrink-0" style={{ borderColor: '#a855f7' }} />
                <span className="flex-1 text-xs">Subcontract</span>
              </div>
            )}
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
                  <p className="text-foreground leading-snug">{String(selectedNode.properties.description)}</p>
                )}
                {!!selectedNode.properties?.contractId && (
                  <p><span className="font-medium">ID:</span>{' '}<span className="font-mono">{String(selectedNode.properties.contractId)}</span></p>
                )}
                {selectedNode.properties?.obligatedAmount != null && (
                  <p><span className="font-medium">Amount:</span> {formatUSD(Number(selectedNode.properties.obligatedAmount))}</p>
                )}
                {!!selectedNode.properties?.signedDate && (
                  <p><span className="font-medium">Signed:</span> {String(selectedNode.properties.signedDate)}</p>
                )}
                {contractRelated?.vendor && (
                  <p><span className="font-medium">Vendor:</span> {contractRelated.vendor}</p>
                )}
                {contractRelated?.awardingAgency && (
                  <p><span className="font-medium">Awarding:</span> {contractRelated.awardingAgency}</p>
                )}
                {contractRelated?.fundingAgency && (
                  <p><span className="font-medium">Funding:</span> {contractRelated.fundingAgency}</p>
                )}
              </div>
            )}

            {(selectedNode.type === 'Vendor') && (
              <div className="pt-1">
                <Link href={`/${selectedNode.type.toLowerCase()}s/detail?id=${selectedNode.id}`} className="text-xs text-primary hover:underline">
                  View detail →
                </Link>
              </div>
            )}
            {(selectedNode.type === 'Agency') && (
              <div className="pt-1">
                <Link href={`/agencies/detail?id=${selectedNode.id}`} className="text-xs text-primary hover:underline">
                  View detail →
                </Link>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 border rounded-lg overflow-hidden bg-muted/20">
        {!graphEnabled && (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
            Search for a vendor or agency to explore the graph.
          </div>
        )}
        {graphEnabled && isLoading && (
          <div className="flex h-full items-center justify-center text-muted-foreground">Loading graph…</div>
        )}
        {graphEnabled && isError && (
          <div className="flex h-full items-center justify-center text-destructive">Failed to load graph.</div>
        )}
        {graphData && graphData.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">No nodes found.</div>
        )}
        {graphData && graphData.nodes.length > 0 && (
          <CytoscapeGraph
            nodes={graphData.nodes}
            edges={graphData.edges}
            highlightedIds={highlightedIds}
            onNodeClick={setSelectedNode}
            layoutName={layoutName}
            layoutOptions={layoutOptions}
          />
        )}
      </div>
    </div>
  );
}
