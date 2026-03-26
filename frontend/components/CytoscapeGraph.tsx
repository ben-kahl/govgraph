'use client';
import { useMemo, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import type { Core } from 'cytoscape';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import cola from 'cytoscape-cola';
import dagre from 'cytoscape-dagre';
import type { GraphNode, GraphEdge } from '@/types/api';

// Register layout plugins once at module load (idempotent)
cytoscape.use(fcose);

/** Pixels between concentric rings when placing expanded nodes. */
const RING_SPACING = 90;
/** Min arc-length between nodes on the same ring (px). */
const NODE_ARC_SPACING = 65;

/**
 * Distribute `ids` into concentric rings around `center`.
 * Ring 1 starts at RING_SPACING px; each subsequent ring adds RING_SPACING.
 * Capacity per ring scales with circumference so nodes stay ~NODE_ARC_SPACING apart.
 */
function placeInRings(cy: Core, center: { x: number; y: number }, ids: string[]) {
  let placed = 0;
  let ring = 1;
  while (placed < ids.length) {
    const r = RING_SPACING * ring;
    const capacity = Math.max(6, Math.floor((2 * Math.PI * r) / NODE_ARC_SPACING));
    const batch = ids.slice(placed, placed + capacity);
    batch.forEach((id, i) => {
      const angle = (2 * Math.PI * i) / batch.length - Math.PI / 2;
      const el = cy.getElementById(id);
      if (el.length > 0) {
        el.position({
          x: center.x + r * Math.cos(angle),
          y: center.y + r * Math.sin(angle),
        });
      }
    });
    placed += batch.length;
    ring++;
  }
}
cytoscape.use(cola);
cytoscape.use(dagre);

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

export interface ClickedEdge {
  id: string;
  label: string;
  source: string;
  target: string;
  weight?: number;
}

export interface LayoutOptions {
  // force-directed (fcose / cose / cola)
  nodeRepulsion?: number;
  idealEdgeLength?: number;
  // dagre
  dagreRankDir?: 'TB' | 'LR';
  dagreRankSep?: number;
  dagreNodeSep?: number;
}

interface CytoscapeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** IDs of seed nodes to highlight with a cyan border */
  highlightedIds?: string[];
  /** IDs of nodes that have been expanded — shown with a green dashed border */
  expandedIds?: string[];
  /** ID of the node most recently double-clicked to expand — new nodes will ring around it */
  expansionRootId?: string | null;
  onNodeClick?: (node: ClickedNode) => void;
  onNodeDoubleClick?: (node: ClickedNode) => void;
  onEdgeClick?: (edge: ClickedEdge) => void;
  layoutName?: string;
  layoutOptions?: LayoutOptions;
}

export function CytoscapeGraph({
  nodes,
  edges,
  highlightedIds,
  expandedIds,
  expansionRootId,
  onNodeClick,
  onNodeDoubleClick,
  onEdgeClick,
  layoutName = 'fcose',
  layoutOptions,
}: CytoscapeGraphProps) {
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onNodeDoubleClickRef = useRef(onNodeDoubleClick);
  onNodeDoubleClickRef.current = onNodeDoubleClick;
  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;

  const cyRef = useRef<Core | null>(null);
  const prevLayoutKeyRef = useRef('');
  const prevNodeIdsRef = useRef<Set<string>>(new Set());

  const elements = useMemo(() => [...nodes, ...edges], [nodes, edges]);

  const layoutConfig = useMemo(() => {
    const cfg: Record<string, unknown> = { name: layoutName };
    if (layoutName === 'fcose' || layoutName === 'cose') {
      cfg.nodeRepulsion = layoutOptions?.nodeRepulsion ?? 8000;
      cfg.idealEdgeLength = layoutOptions?.idealEdgeLength ?? 100;
    } else if (layoutName === 'cola') {
      // Cola uses edgeLength instead of idealEdgeLength; animate:false avoids
      // re-layout thrash on stylesheet updates
      if (layoutOptions?.idealEdgeLength !== undefined) cfg.edgeLength = layoutOptions.idealEdgeLength;
      cfg.animate = false;
      cfg.maxSimulationTime = 3000;
    } else if (layoutName === 'dagre') {
      cfg.rankDir = layoutOptions?.dagreRankDir ?? 'TB';
      cfg.rankSep = layoutOptions?.dagreRankSep ?? 80;
      cfg.nodeSep = layoutOptions?.dagreNodeSep ?? 40;
      cfg.animate = false;
    }
    return cfg;
  }, [layoutName, layoutOptions]);

  const stylesheet = useMemo(
    () => [
      // --- Base node style ---
      {
        selector: 'node',
        style: {
          width: 60,
          height: 60,
          'font-size': '10px',
          color: '#fff',
          'text-valign': 'center' as const,
          'text-halign': 'center' as const,
          'text-wrap': 'wrap' as const,
          'text-max-width': '50px',
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
        style: {
          'background-color': '#f59e0b',
          shape: 'rectangle' as const,
          width: 45,
          height: 45,
          'font-size': '8px',
          'text-max-width': '38px',
        },
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
        style: { width: 45, height: 45, 'font-size': '9px' },
      },

      // --- Highlighted seed nodes ---
      ...(highlightedIds?.length
        ? highlightedIds.map((id) => ({
          selector: `node[id = "${id}"]`,
          style: { 'border-width': 3, 'border-color': '#22d3ee' },
        }))
        : []),

      // --- Expanded nodes (double-clicked) ---
      ...(expandedIds?.length
        ? expandedIds.map((id) => ({
          selector: `node[id = "${id}"]`,
          style: { 'border-width': 3, 'border-color': '#a855f7', 'border-style': 'dashed' as const },
        }))
        : []),

      // --- Base edge style ---
      {
        selector: 'edge',
        style: {
          width: 1,
          'line-color': '#64748b',
          'target-arrow-color': '#64748b',
          'target-arrow-shape': 'triangle' as const,
          'curve-style': 'bezier' as const,
          opacity: 0.7,
        },
      },

      // --- Edge colors by relationship type ---
      {
        selector: 'edge[label = "AWARDED"]',
        style: { 'line-color': '#ef4444', 'target-arrow-color': '#ef4444' },
      },
      {
        selector: 'edge[label = "AWARDED_CONTRACT"]',
        style: { 'line-color': '#22c55e', 'target-arrow-color': '#22c55e' },
      },
      {
        selector: 'edge[label = "FUNDED"]',
        style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b' },
      },
      {
        selector: 'edge[label = "SUBAGENCY_OF"]',
        style: { 'line-color': '#64748b', 'target-arrow-color': '#64748b' },
      },
      {
        selector: 'edge[label = "SUBCONTRACTED"]',
        style: {
          'line-color': '#a855f7',
          'target-arrow-color': '#a855f7',
          'line-style': 'dashed' as const,
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

      // --- Selected edge highlight ---
      {
        selector: 'edge:selected',
        style: { opacity: 1, width: 3 },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [highlightedIds?.join(','), expandedIds?.join(',')]
  );

  // Stable refs used inside effects to avoid stale closures without re-subscribing
  const layoutConfigRef = useRef(layoutConfig);
  layoutConfigRef.current = layoutConfig;
  const expansionRootIdRef = useRef(expansionRootId);
  expansionRootIdRef.current = expansionRootId;

  // Re-run layout when layoutName or layoutOptions change
  useEffect(() => {
    const key = JSON.stringify(layoutConfig);
    if (cyRef.current && key !== prevLayoutKeyRef.current) {
      prevLayoutKeyRef.current = key;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      cyRef.current.layout(layoutConfig as any).run();
    }
  }, [layoutConfig]);

  // Handle element changes: position new nodes concentrically around expansion root,
  // or re-run the layout when nodes are removed (collapse/clear).
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const currentIds = new Set(nodes.map((n) => n.data.id));
    const prevIds = prevNodeIdsRef.current;
    const addedIds = nodes.map((n) => n.data.id).filter((id) => !prevIds.has(id));
    const hadExisting = prevIds.size > 0;

    if (addedIds.length > 0 && hadExisting) {
      const rootId = expansionRootIdRef.current;
      const rootEl = rootId ? cy.getElementById(rootId) : null;

      if (rootEl && rootEl.length > 0) {
        // Existing nodes (excluding the root and the newly added ones)
        const addedSet = new Set(addedIds);
        const existingNodes = cy.nodes().filter(
          (n) => n.id() !== rootId && !addedSet.has(n.id())
        );

        // Move the root away from the existing cluster to create space for the ring
        let newCenter = rootEl.position();
        if (existingNodes.length > 0) {
          const bb = existingNodes.boundingBox({});
          const centroidX = (bb.x1 + bb.x2) / 2;
          const centroidY = (bb.y1 + bb.y2) / 2;
          const rootPos = rootEl.position();
          const dx = rootPos.x - centroidX;
          const dy = rootPos.y - centroidY;
          const dist = Math.hypot(dx, dy) || 1;
          // Estimate how many rings we'll need, move root far enough to clear them
          const ringCount = Math.ceil(addedIds.length / 8) + 1;
          const expansionRadius = RING_SPACING * ringCount;
          const moveBy = expansionRadius + 80;
          newCenter = {
            x: rootPos.x + (dx / dist) * moveBy,
            y: rootPos.y + (dy / dist) * moveBy,
          };
          rootEl.position(newCenter);
        }

        // Place new nodes in concentric rings around the (moved) root
        placeInRings(cy, newCenter, addedIds);

        // Center the view on the expansion root + its new neighbors
        const expansionEles = cy.getElementById(rootId!).union(
          cy.nodes().filter((n) => addedSet.has(n.id()))
        );
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        cy.animate({ fit: { eles: expansionEles as any, padding: 80 } } as any, { duration: 400 });
      } else {
        // No known root — re-run full layout
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        cy.layout(layoutConfigRef.current as any).run();
      }
    } else if (currentIds.size < prevIds.size && hadExisting) {
      // Nodes removed (collapse or clear) — re-run layout to close the gaps
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      cy.layout(layoutConfigRef.current as any).run();
    }

    prevNodeIdsRef.current = currentIds;
  }, [nodes, edges]);

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
    cy.off('dbltap', 'node');
    cy.on('dbltap', 'node', (evt) => {
      const n = evt.target;
      onNodeDoubleClickRef.current?.({
        id: n.id(),
        label: n.data('label'),
        type: n.data('type'),
        properties: n.data('properties'),
      });
    });
    cy.off('tap', 'edge');
    cy.on('tap', 'edge', (evt) => {
      const e = evt.target;
      onEdgeClickRef.current?.({
        id: e.id(),
        label: e.data('label'),
        source: e.data('source'),
        target: e.data('target'),
        weight: e.data('weight'),
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
