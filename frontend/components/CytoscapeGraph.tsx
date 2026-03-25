'use client';
import { useMemo, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import type { Core } from 'cytoscape';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import cola from 'cytoscape-cola';
import type { GraphNode, GraphEdge } from '@/types/api';

// Register layout plugins once at module load (idempotent)
cytoscape.use(fcose);
cytoscape.use(cola);

const CytoscapeComponent = dynamic(() => import('react-cytoscapejs'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      Loading graph…
    </div>
  ),
});

export interface ClickedNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface LayoutOptions {
  nodeRepulsion?: number;
  idealEdgeLength?: number;
}

interface CytoscapeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** IDs of seed nodes to highlight with a cyan border */
  highlightedIds?: string[];
  onNodeClick?: (node: ClickedNode) => void;
  layoutName?: string;
  layoutOptions?: LayoutOptions;
}

export function CytoscapeGraph({
  nodes,
  edges,
  highlightedIds,
  onNodeClick,
  layoutName = 'fcose',
  layoutOptions,
}: CytoscapeGraphProps) {
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  const cyRef = useRef<Core | null>(null);
  const prevLayoutKeyRef = useRef('');

  const elements = useMemo(() => [...nodes, ...edges], [nodes, edges]);

  const layoutConfig = useMemo(() => {
    const cfg: Record<string, unknown> = { name: layoutName };
    if (layoutName === 'fcose' || layoutName === 'cose') {
      if (layoutOptions?.nodeRepulsion !== undefined) cfg.nodeRepulsion = layoutOptions.nodeRepulsion;
      if (layoutOptions?.idealEdgeLength !== undefined) cfg.idealEdgeLength = layoutOptions.idealEdgeLength;
    } else if (layoutName === 'cola') {
      // Cola uses edgeLength instead of idealEdgeLength; animate:false avoids
      // re-layout thrash on stylesheet updates
      if (layoutOptions?.idealEdgeLength !== undefined) cfg.edgeLength = layoutOptions.idealEdgeLength;
      cfg.animate = false;
      cfg.maxSimulationTime = 3000;
    }
    return cfg;
  }, [layoutName, layoutOptions]);

  const stylesheet = useMemo(
    () => [
      // --- Base node style ---
      {
        selector: 'node',
        style: {
          width: 65,
          height: 65,
          'font-size': '10px',
          color: '#fff',
          'text-valign': 'center' as const,
          'text-halign': 'center' as const,
          'text-wrap': 'wrap' as const,
          'text-max-width': '55px',
          label: 'data(label)',
        },
      },
      {
        selector: 'node[type="Vendor"]',
        style: { 'background-color': '#ef4444' },
      },
      {
        selector: 'node[type="Agency"]',
        style: { 'background-color': '#22c55e' },
      },
      {
        selector: 'node[type="Contract"]',
        style: { 'background-color': '#f59e0b', shape: 'rectangle' as const },
      },

      // --- Vendor node sizing by total contract value ---
      {
        selector: 'node[type="Vendor"][weight >= 10000000]',      // $10M+
        style: { width: 70, height: 70 },
      },
      {
        selector: 'node[type="Vendor"][weight >= 100000000]',     // $100M+
        style: { width: 80, height: 80 },
      },
      {
        selector: 'node[type="Vendor"][weight >= 1000000000]',    // $1B+
        style: { width: 95, height: 95 },
      },

      // --- Agency hierarchy: sub-agencies rendered smaller ---
      {
        selector: 'node[type="Agency"][?isSubagency]',
        style: { width: 50, height: 50 },
      },

      // --- Highlighted seed nodes ---
      ...(highlightedIds?.length
        ? highlightedIds.map((id) => ({
          selector: `node[id = "${id}"]`,
          style: { 'border-width': 3, 'border-color': '#22d3ee' },
        }))
        : []),

      // --- Base edge style ---
      {
        selector: 'edge',
        style: {
          width: 1,
          'line-color': '#94a3b8',
          'target-arrow-color': '#94a3b8',
          'target-arrow-shape': 'triangle' as const,
          'curve-style': 'bezier' as const,
          label: 'data(label)',
          'font-size': '8px',
          color: 'black',
          'text-rotation': 'autorotate' as const,
        },
      },

      // --- Edge width by obligated amount (stepped thresholds) ---
      {
        selector: 'edge[weight >= 100000]',     // $100K+
        style: { width: 2 },
      },
      {
        selector: 'edge[weight >= 1000000]',    // $1M+
        style: { width: 3 },
      },
      {
        selector: 'edge[weight >= 10000000]',   // $10M+
        style: { width: 5 },
      },
      {
        selector: 'edge[weight >= 100000000]',  // $100M+
        style: { width: 7 },
      },

      // --- Subcontract edges — dashed purple ---
      {
        selector: 'edge[label = "SUBCONTRACTED"]',
        style: {
          'line-color': '#a855f7',
          'target-arrow-color': '#a855f7',
          'line-style': 'dashed' as const,
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [highlightedIds?.join(',')]
  );

  // Re-run layout when layoutName or layoutOptions change
  useEffect(() => {
    const key = JSON.stringify(layoutConfig);
    if (cyRef.current && key !== prevLayoutKeyRef.current) {
      prevLayoutKeyRef.current = key;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      cyRef.current.layout(layoutConfig as any).run();
    }
  }, [layoutConfig]);

  const handleCy = useCallback((cy: Core) => {
    cyRef.current = cy;
    cy.off('tap', 'node');
    cy.on('tap', 'node', (evt) => {
      const n = evt.target;
      onNodeClickRef.current?.({
        id: n.id(),
        label: n.data('label'),
        type: n.data('type'),
        properties: n.data('properties'),
      });
    });
  }, []);

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: '100%', height: '100%' }}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      layout={layoutConfig as any}
      stylesheet={stylesheet}
      minZoom={0.2}
      maxZoom={3}
      cy={handleCy}
    />
  );
}
