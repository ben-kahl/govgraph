'use client';
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { formatUSD } from '@/lib/utils';
import { CytoscapeGraph } from '@/components/CytoscapeGraph';
import type { ClickedNode, ClickedEdge, LayoutOptions } from '@/components/CytoscapeGraph';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { GraphNode, GraphEdge, GraphResponse } from '@/types/api';

type Mode = 'vendor' | 'agency' | 'overview' | 'explore' | 'path';
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

const EDGE_COLORS: Record<string, string> = {
  AWARDED: '#ef4444',
  AWARDED_CONTRACT: '#22c55e',
  FUNDED: '#f59e0b',
  SUBAGENCY_OF: '#64748b',
  SUBCONTRACTED: '#a855f7',
};

const LAYOUTS = [
  { value: 'dagre', label: 'Dagre (hierarchical)' },
  { value: 'fcose', label: 'fCOSE (force-directed)' },
  { value: 'cola', label: 'Cola (constraint-based)' },
  { value: 'breadthfirst', label: 'Breadth-first' },
  { value: 'cose', label: 'CoSE (force-directed)' },
  { value: 'circle', label: 'Circle' },
  { value: 'grid', label: 'Grid' },
  { value: 'concentric', label: 'Concentric' },
];


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
  const [exploreActive, setExploreActive] = useState(false);
  const [selectedNode, setSelectedNode] = useState<ClickedNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ClickedEdge | null>(null);
  const [layoutName, setLayoutName] = useState('fcose');
  const [nodeRepulsion, setNodeRepulsion] = useState(8000);
  const [idealEdgeLength, setIdealEdgeLength] = useState(100);
  const [dagreRankDir, setDagreRankDir] = useState<'TB' | 'LR'>('TB');
  const [dagreRankSep, setDagreRankSep] = useState(80);
  const [dagreNodeSep, setDagreNodeSep] = useState(40);
  const [contractLimit, setContractLimit] = useState(500);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  // Path mode state
  const [pathFrom, setPathFrom] = useState<SelectedEntity | null>(null);
  const [pathTo, setPathTo] = useState<SelectedEntity | null>(null);
  const [pathFromSearch, setPathFromSearch] = useState('');
  const [pathFromDebounced, setPathFromDebounced] = useState('');
  const [pathToSearch, setPathToSearch] = useState('');
  const [pathToDebounced, setPathToDebounced] = useState('');
  const [pathActive, setPathActive] = useState(false);
  const [expansions, setExpansions] = useState<Map<string, GraphResponse>>(() => new Map());
  const [expansionRootId, setExpansionRootId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(t);
  }, [searchText]);

  useEffect(() => {
    const t = setTimeout(() => setPathFromDebounced(pathFromSearch), 300);
    return () => clearTimeout(t);
  }, [pathFromSearch]);

  useEffect(() => {
    const t = setTimeout(() => setPathToDebounced(pathToSearch), 300);
    return () => clearTimeout(t);
  }, [pathToSearch]);

  const { data: suggestions } = useQuery({
    queryKey: ['graph-search', mode, debouncedSearch],
    queryFn: async () => {
      if (mode === 'vendor') {
        const r = await api.vendors.list(debouncedSearch, 1, 8);
        return r.items.map((v) => ({ id: v.id, name: v.canonical_name }));
      }
      const r = await api.agencies.list(debouncedSearch, 1, 8);
      return r.items.map((a) => ({
        id: a.id,
        name: a.agency_code ? `${a.agency_name} (${a.agency_code})` : a.agency_name,
      }));
    },
    enabled: (mode === 'vendor' || mode === 'agency') && debouncedSearch.length >= 2,
  });

  const { data: pathFromSuggestions } = useQuery({
    queryKey: ['path-from-search', pathFromDebounced],
    queryFn: async () => {
      const [vendors, agencies] = await Promise.all([
        api.vendors.list(pathFromDebounced, 1, 5),
        api.agencies.list(pathFromDebounced, 1, 5),
      ]);
      return [
        ...vendors.items.map((v) => ({ id: v.id, name: v.canonical_name, type: 'vendor' as EntityMode })),
        ...agencies.items.map((a) => ({ id: a.id, name: a.agency_name, type: 'agency' as EntityMode })),
      ];
    },
    enabled: mode === 'path' && pathFromDebounced.length >= 2,
  });

  const { data: pathToSuggestions } = useQuery({
    queryKey: ['path-to-search', pathToDebounced],
    queryFn: async () => {
      const [vendors, agencies] = await Promise.all([
        api.vendors.list(pathToDebounced, 1, 5),
        api.agencies.list(pathToDebounced, 1, 5),
      ]);
      return [
        ...vendors.items.map((v) => ({ id: v.id, name: v.canonical_name, type: 'vendor' as EntityMode })),
        ...agencies.items.map((a) => ({ id: a.id, name: a.agency_name, type: 'agency' as EntityMode })),
      ];
    },
    enabled: mode === 'path' && pathToDebounced.length >= 2,
  });

  const graphEnabled = overviewActive || exploreActive || selectedEntities.length > 0 || pathActive;
  const queryKey = overviewActive
    ? ['graph', 'overview']
    : exploreActive
    ? ['graph', 'explore']
    : pathActive && pathFrom && pathTo
    ? ['graph', 'path', pathFrom.id, pathTo.id, pathFrom.type, pathTo.type]
    : ['graph', 'entities', selectedEntities.map((e) => `${e.type}:${e.id}`).join(','), contractLimit];

  const { data: graphData, isLoading, isError } = useQuery({
    queryKey,
    queryFn: async () => {
      if (overviewActive) return api.graph.overview();
      if (exploreActive) return api.graph.explore();
      if (pathActive && pathFrom && pathTo) return api.graph.path(pathFrom.id, pathTo.id, pathFrom.type, pathTo.type);
      const results = await Promise.all(
        selectedEntities.map((e) =>
          e.type === 'vendor'
            ? api.graph.vendor(e.id, contractLimit)
            : api.graph.agency(e.id, contractLimit)
        )
      );
      return mergeGraphResponses(results);
    },
    enabled: graphEnabled,
  });

  // Merge base query result with any manually expanded subgraphs
  const allGraphData = useMemo(() => {
    if (!graphData && expansions.size === 0) return undefined;
    const base = graphData ?? { nodes: [], edges: [] };
    if (expansions.size === 0) return base;
    return mergeGraphResponses([base, ...expansions.values()]);
  }, [graphData, expansions]);

  // Client-side date filter: hide Contract nodes outside [dateFrom, dateTo]
  const displayedGraphData = useMemo(() => {
    if (!allGraphData || (!dateFrom && !dateTo)) return allGraphData;
    const from = dateFrom ? new Date(dateFrom).getTime() : -Infinity;
    const to = dateTo ? new Date(dateTo + 'T23:59:59').getTime() : Infinity;

    const hiddenIds = new Set(
      allGraphData.nodes
        .filter((n) => {
          if (n.data.type !== 'Contract') return false;
          const d = n.data.properties?.signedDate as string | undefined;
          if (!d) return false;
          const t = new Date(d).getTime();
          return t < from || t > to;
        })
        .map((n) => n.data.id)
    );

    if (hiddenIds.size === 0) return allGraphData;
    return {
      nodes: allGraphData.nodes.filter((n) => !hiddenIds.has(n.data.id)),
      edges: allGraphData.edges.filter(
        (e) => !hiddenIds.has(e.data.source) && !hiddenIds.has(e.data.target)
      ),
    };
  }, [allGraphData, dateFrom, dateTo]);

  const highlightedIds = useMemo(() => {
    if (overviewActive || exploreActive) return [];
    if (pathActive && pathFrom && pathTo) return [pathFrom.id, pathTo.id];
    return selectedEntities.map((e) => e.id);
  }, [overviewActive, exploreActive, pathActive, pathFrom, pathTo, selectedEntities]);

  const layoutOptions = useMemo<LayoutOptions | undefined>(() => {
    if (layoutName === 'fcose' || layoutName === 'cose' || layoutName === 'cola') {
      return { nodeRepulsion, idealEdgeLength };
    }
    if (layoutName === 'dagre') {
      return { dagreRankDir, dagreRankSep, dagreNodeSep };
    }
    return undefined;
  }, [layoutName, nodeRepulsion, idealEdgeLength, dagreRankDir, dagreRankSep, dagreNodeSep]);

  const hasContracts = allGraphData?.nodes.some(
    (n) => n.data.type === 'Contract' && n.data.properties?.signedDate
  ) ?? false;

  function addEntity(id: string, name: string) {
    if (selectedEntities.some((e) => e.id === id)) return;
    setSelectedEntities((prev) => [...prev, { id, name, type: mode as EntityMode }]);
    setExpansions(new Map());
    setExpansionRootId(null);
    setSearchText('');
    setShowDropdown(false);
    setSelectedNode(null);
    setSelectedEdge(null);
    if (overviewActive) setOverviewActive(false);
    if (exploreActive) setExploreActive(false);
  }

  function removeEntity(id: string) {
    setSelectedEntities((prev) => prev.filter((e) => e.id !== id));
    setExpansions(new Map());
    setExpansionRootId(null);
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  function switchMode(newMode: Mode) {
    setMode(newMode);
    setExpansions(new Map());
    setExpansionRootId(null);
    setSearchText('');
    setDebouncedSearch('');
    setShowDropdown(false);
    setSelectedNode(null);
    setSelectedEdge(null);
    if (newMode !== 'overview') setOverviewActive(false);
    if (newMode !== 'explore') setExploreActive(false);
    if (newMode !== 'path') { setPathActive(false); setPathFrom(null); setPathTo(null); setPathFromSearch(''); setPathToSearch(''); }
  }

  function loadOverview() {
    setOverviewActive(true);
    setExploreActive(false);
    setSelectedEntities([]);
    setExpansions(new Map());
    setExpansionRootId(null);
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  function loadExplore() {
    setExploreActive(true);
    setOverviewActive(false);
    setSelectedEntities([]);
    setExpansions(new Map());
    setExpansionRootId(null);
    setSelectedNode(null);
    setSelectedEdge(null);
  }

  async function expandNode(node: ClickedNode) {
    // Toggle: if already expanded, collapse by removing its data
    if (expansions.has(node.id)) {
      setExpansionRootId(null);
      setExpansions((prev) => {
        const next = new Map(prev);
        next.delete(node.id);
        return next;
      });
      return;
    }
    try {
      let result: GraphResponse;
      if (node.type === 'Vendor') {
        result = await api.graph.vendor(node.id, contractLimit);
      } else if (node.type === 'Agency') {
        result = await api.graph.agency(node.id, contractLimit);
      } else {
        result = await api.graph.contract(node.id);
      }
      setExpansionRootId(node.id);
      setExpansions((prev) => new Map(prev).set(node.id, result));
    } catch {
      // node may not exist in graph DB — fail silently
    }
  }

  const legendCounts = displayedGraphData?.nodes.reduce<Record<string, number>>((acc, n) => {
    const t = n.data.type;
    acc[t] = (acc[t] ?? 0) + 1;
    return acc;
  }, {}) ?? {};

  const contractRelated =
    selectedNode?.type === 'Contract' && displayedGraphData
      ? getContractRelated(selectedNode.id, displayedGraphData)
      : null;

  const nodeLabel = useMemo(() => {
    if (!displayedGraphData) return (id: string) => id;
    const map = new Map(displayedGraphData.nodes.map((n) => {
      const d = n.data;
      const name = (d.properties?.canonicalName ?? d.properties?.agencyName ?? d.label) as string;
      return [d.id, name];
    }));
    return (id: string) => map.get(id) ?? id;
  }, [displayedGraphData]);

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
          <Button variant={mode === 'explore' ? 'default' : 'outline'} size="sm" onClick={() => switchMode('explore')}>
            Explore
          </Button>
          <Button variant={mode === 'path' ? 'default' : 'outline'} size="sm" onClick={() => switchMode('path')}>
            Path
          </Button>
        </div>

        {/* Search / action panel */}
        {(mode === 'vendor' || mode === 'agency') && (
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
        )}

        {mode === 'overview' && (
          <div className="space-y-2">
            <Button className="w-full" onClick={loadOverview}>
              Load market overview
            </Button>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Shows the top 30 vendors by total contract value, the contracts they
              were awarded, and the agencies that funded them. Larger vendor nodes
              and thicker edges indicate higher dollar amounts.
            </p>
          </div>
        )}

        {mode === 'explore' && (
          <div className="space-y-2">
            <Button className="w-full" onClick={loadExplore}>
              Explore dataset
            </Button>
            <p className="text-xs text-muted-foreground leading-relaxed">
              A broad starting view: the top federal agencies, their sub-agencies,
              and the highest-value contracts ($5M+) they awarded along with the
              winning vendors. Good for discovering patterns across the dataset.
            </p>
          </div>
        )}

        {mode === 'path' && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Find the shortest relationship path between any two vendors or agencies in the graph.
            </p>

            {/* From entity */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">From</label>
              {pathFrom ? (
                <div className="flex items-center gap-1.5 rounded border px-2 py-1.5 text-xs">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: pathFrom.type === 'vendor' ? '#ef4444' : '#22c55e' }}
                  />
                  <span className="flex-1 truncate">{pathFrom.name}</span>
                  <button
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => { setPathFrom(null); setPathActive(false); }}
                  >×</button>
                </div>
              ) : (
                <div className="relative">
                  <Input
                    placeholder="Search vendors or agencies…"
                    value={pathFromSearch}
                    onChange={(e) => setPathFromSearch(e.target.value)}
                  />
                  {pathFromSuggestions && pathFromSuggestions.length > 0 && pathFromSearch.length >= 2 && (
                    <ul className="absolute z-10 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-48 overflow-auto">
                      {pathFromSuggestions.map((item) => (
                        <li
                          key={item.id}
                          className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-accent"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => { setPathFrom(item); setPathFromSearch(''); }}
                        >
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: item.type === 'vendor' ? '#ef4444' : '#22c55e' }}
                          />
                          {item.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            {/* To entity */}
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">To</label>
              {pathTo ? (
                <div className="flex items-center gap-1.5 rounded border px-2 py-1.5 text-xs">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: pathTo.type === 'vendor' ? '#ef4444' : '#22c55e' }}
                  />
                  <span className="flex-1 truncate">{pathTo.name}</span>
                  <button
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => { setPathTo(null); setPathActive(false); }}
                  >×</button>
                </div>
              ) : (
                <div className="relative">
                  <Input
                    placeholder="Search vendors or agencies…"
                    value={pathToSearch}
                    onChange={(e) => setPathToSearch(e.target.value)}
                  />
                  {pathToSuggestions && pathToSuggestions.length > 0 && pathToSearch.length >= 2 && (
                    <ul className="absolute z-10 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-48 overflow-auto">
                      {pathToSuggestions.map((item) => (
                        <li
                          key={item.id}
                          className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-accent"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => { setPathTo(item); setPathToSearch(''); }}
                        >
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: item.type === 'vendor' ? '#ef4444' : '#22c55e' }}
                          />
                          {item.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <Button
              className="w-full"
              disabled={!pathFrom || !pathTo}
              onClick={() => { setPathActive(true); setExpansions(new Map()); setSelectedNode(null); setSelectedEdge(null); }}
            >
              Find Path
            </Button>

            {pathActive && graphData && graphData.nodes.length === 0 && (
              <p className="text-xs text-muted-foreground">No path found between these entities.</p>
            )}
          </div>
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

        {/* Contract limit */}
        {(mode === 'vendor' || mode === 'agency') && (
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Contract limit</label>
            <select
              value={contractLimit}
              onChange={(e) => setContractLimit(Number(e.target.value))}
              className="w-full border rounded px-2 py-1 text-sm bg-background"
            >
              <option value={200}>Top 200 by value</option>
              <option value={500}>Top 500 by value</option>
              <option value={1000}>Top 1,000 by value</option>
              <option value={5000}>Top 5,000 by value</option>
            </select>
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

          {layoutName === 'dagre' && (
            <div className="space-y-2 pl-1">
              <div className="space-y-0.5">
                <label className="text-xs text-muted-foreground">Direction</label>
                <select
                  value={dagreRankDir}
                  onChange={(e) => setDagreRankDir(e.target.value as 'TB' | 'LR')}
                  className="w-full border rounded px-2 py-1 text-sm bg-background"
                >
                  <option value="TB">Top → Bottom</option>
                  <option value="LR">Left → Right</option>
                </select>
              </div>
              <div className="space-y-0.5">
                <div className="flex justify-between">
                  <label className="text-xs text-muted-foreground">Rank Spacing</label>
                  <span className="text-xs text-muted-foreground">{dagreRankSep}</span>
                </div>
                <input
                  type="range"
                  min={20}
                  max={300}
                  step={10}
                  value={dagreRankSep}
                  onChange={(e) => setDagreRankSep(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              <div className="space-y-0.5">
                <div className="flex justify-between">
                  <label className="text-xs text-muted-foreground">Node Spacing</label>
                  <span className="text-xs text-muted-foreground">{dagreNodeSep}</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={200}
                  step={10}
                  value={dagreNodeSep}
                  onChange={(e) => setDagreNodeSep(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
          )}

          {(layoutName === 'fcose' || layoutName === 'cose' || layoutName === 'cola') && (
            <div className="space-y-2 pl-1">
              {(layoutName === 'fcose' || layoutName === 'cose') && (
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
              )}
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
        {displayedGraphData && displayedGraphData.nodes.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">Nodes</p>
            {(mode === 'vendor' || mode === 'agency') && !overviewActive && !exploreActive && (
              <p className="text-xs text-muted-foreground italic">
                Showing top {contractLimit.toLocaleString()} contracts by value
              </p>
            )}
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
            {(() => {
              const edgeTypes = [...new Set(displayedGraphData.edges.map((e) => e.data.label))];
              if (edgeTypes.length === 0) return null;
              return (
                <>
                  <p className="text-sm font-medium text-muted-foreground pt-1">Edges</p>
                  {edgeTypes.map((label) => (
                    <div key={label} className="flex items-center gap-2 text-xs">
                      <span
                        className="inline-block w-6 h-0 border-t-2 shrink-0"
                        style={{
                          borderColor: EDGE_COLORS[label] ?? '#64748b',
                          borderStyle: label === 'SUBCONTRACTED' ? 'dashed' : 'solid',
                        }}
                      />
                      <span className="flex-1 text-muted-foreground">{label}</span>
                    </div>
                  ))}
                </>
              );
            })()}
          </div>
        )}

        {/* Expansion hint / controls */}
        {graphEnabled && !isLoading && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">
              Double-click any node to expand its connections · double-click again to collapse
            </p>
            {expansions.size > 0 && (
              <button
                className="text-xs text-muted-foreground hover:text-destructive"
                onClick={() => { setExpansions(new Map()); setExpansionRootId(null); }}
              >
                Clear expansions ({expansions.size})
              </button>
            )}
          </div>
        )}

        {/* Date filter — shown when graph has contracts with signedDate */}
        {hasContracts && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">Filter by Date</p>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground block">
                From
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  aria-label="Date from"
                  className="mt-0.5 w-full border rounded px-2 py-1 text-xs bg-background block"
                />
              </label>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground block">
                To
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  aria-label="Date to"
                  className="mt-0.5 w-full border rounded px-2 py-1 text-xs bg-background block"
                />
              </label>
            </div>
            {(dateFrom || dateTo) && (
              <button
                onClick={() => { setDateFrom(''); setDateTo(''); }}
                className="text-xs text-muted-foreground hover:text-destructive"
              >
                Clear filter
              </button>
            )}
          </div>
        )}

        {/* Selected node panel */}
        {selectedEdge && (
          <div className="rounded-lg border p-3 space-y-2">
            <div className="flex items-center gap-2">
              <span
                className="inline-block w-8 h-0 border-t-2 shrink-0"
                style={{
                  borderColor: EDGE_COLORS[selectedEdge.label] ?? '#64748b',
                  borderStyle: selectedEdge.label === 'SUBCONTRACTED' ? 'dashed' : 'solid',
                }}
              />
              <span
                className="inline-block px-2 py-0.5 rounded text-xs text-white"
                style={{ backgroundColor: EDGE_COLORS[selectedEdge.label] ?? '#64748b' }}
              >
                {selectedEdge.label}
              </span>
            </div>
            <div className="space-y-1 pt-1 text-xs text-muted-foreground">
              <p><span className="font-medium">From:</span>{' '}{nodeLabel(selectedEdge.source)}</p>
              <p><span className="font-medium">To:</span>{' '}{nodeLabel(selectedEdge.target)}</p>
              {selectedEdge.weight != null && (
                <p><span className="font-medium">Amount:</span>{' '}{formatUSD(selectedEdge.weight)}</p>
              )}
            </div>
          </div>
        )}

        {selectedNode && (
          <div className="rounded-lg border p-3 space-y-2">
            <p className="text-sm font-medium leading-snug">
              {selectedNode.type === 'Vendor' && selectedNode.properties?.canonicalName
                ? String(selectedNode.properties.canonicalName)
                : selectedNode.type === 'Agency' && selectedNode.properties?.agencyName
                ? String(selectedNode.properties.agencyName)
                : selectedNode.label}
            </p>
            <span
              className="inline-block px-2 py-0.5 rounded text-xs text-white"
              style={{ backgroundColor: NODE_COLORS[selectedNode.type] ?? '#94a3b8' }}
            >
              {selectedNode.type}
            </span>

            {selectedNode.type === 'Vendor' && (
              <div className="space-y-1.5 pt-1 text-xs text-muted-foreground">
                <p><span className="font-medium">ID:</span>{' '}<span className="font-mono break-all">{selectedNode.id}</span></p>
                {selectedNode.properties?.totalContractValue != null && (
                  <p><span className="font-medium">Total Obligated:</span>{' '}{formatUSD(Number(selectedNode.properties.totalContractValue))}</p>
                )}
                <div className="pt-1">
                  <Link href={`/vendors/detail?id=${selectedNode.id}`} className="text-primary hover:underline">
                    View detail →
                  </Link>
                </div>
              </div>
            )}

            {selectedNode.type === 'Agency' && (
              <div className="space-y-1.5 pt-1 text-xs text-muted-foreground">
                <p><span className="font-medium">ID:</span>{' '}<span className="font-mono break-all">{selectedNode.id}</span></p>
                {!!selectedNode.properties?.agencyCode && (
                  <p><span className="font-medium">Code:</span>{' '}<span className="font-mono">{String(selectedNode.properties.agencyCode)}</span></p>
                )}
                <div className="pt-1">
                  <Link href={`/agencies/detail?id=${selectedNode.id}`} className="text-primary hover:underline">
                    View detail →
                  </Link>
                </div>
              </div>
            )}

            {selectedNode.type === 'Contract' && (
              <div className="space-y-1.5 pt-1 text-xs text-muted-foreground">
                {!!selectedNode.properties?.description && (
                  <p className="text-foreground leading-snug">{String(selectedNode.properties.description)}</p>
                )}
                {!!selectedNode.properties?.contractId && (
                  <p><span className="font-medium">ID:</span>{' '}<span className="font-mono">{String(selectedNode.properties.contractId)}</span></p>
                )}
                {selectedNode.properties?.obligatedAmount != null && (
                  <p><span className="font-medium">Amount:</span>{' '}{formatUSD(Number(selectedNode.properties.obligatedAmount))}</p>
                )}
                {!!selectedNode.properties?.signedDate && (
                  <p><span className="font-medium">Signed:</span>{' '}{String(selectedNode.properties.signedDate)}</p>
                )}
                {!!selectedNode.properties?.awardType && (
                  <p><span className="font-medium">Type:</span>{' '}{String(selectedNode.properties.awardType)}</p>
                )}
                {contractRelated?.vendor && (
                  <p><span className="font-medium">Vendor:</span>{' '}{contractRelated.vendor}</p>
                )}
                {contractRelated?.awardingAgency && (
                  <p><span className="font-medium">Awarding:</span>{' '}{contractRelated.awardingAgency}</p>
                )}
                {contractRelated?.fundingAgency && (
                  <p><span className="font-medium">Funding:</span>{' '}{contractRelated.fundingAgency}</p>
                )}
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
        {displayedGraphData && displayedGraphData.nodes.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">No nodes found.</div>
        )}
        {displayedGraphData && displayedGraphData.nodes.length > 0 && (
          <CytoscapeGraph
            nodes={displayedGraphData.nodes}
            edges={displayedGraphData.edges}
            highlightedIds={highlightedIds}
            expandedIds={[...expansions.keys()]}
            expansionRootId={expansionRootId}
            onNodeClick={(node) => { setSelectedNode(node); setSelectedEdge(null); }}
            onNodeDoubleClick={expandNode}
            onEdgeClick={(edge) => { setSelectedEdge(edge); setSelectedNode(null); }}
            layoutName={layoutName}
            layoutOptions={layoutOptions}
          />
        )}
      </div>
    </div>
  );
}
