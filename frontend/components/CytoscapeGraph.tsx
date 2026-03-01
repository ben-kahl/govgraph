'use client';
import { useMemo, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
import type { Core } from 'cytoscape';
import type { GraphNode, GraphEdge } from '@/types/api';

const CytoscapeComponent = dynamic(() => import('react-cytoscapejs'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      Loading graph…
    </div>
  ),
});

interface CytoscapeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedId?: string;
  onNodeClick?: (node: { id: string; label: string; type: string }) => void;
}

export function CytoscapeGraph({ nodes, edges, highlightedId, onNodeClick }: CytoscapeGraphProps) {
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  const elements = useMemo(() => [...nodes, ...edges], [nodes, edges]);

  const stylesheet = useMemo(
    () => [
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
      ...(highlightedId
        ? [
            {
              selector: `node[id = "${highlightedId}"]`,
              style: {
                'border-width': 3,
                'border-color': '#22d3ee',
              },
            },
          ]
        : []),
      {
        selector: 'edge',
        style: {
          'line-color': '#94a3b8',
          'target-arrow-color': '#94a3b8',
          'target-arrow-shape': 'triangle' as const,
          'curve-style': 'bezier' as const,
          label: 'data(label)',
          'font-size': '8px',
          color: '#94a3b8',
          'text-rotation': 'autorotate' as const,
        },
      },
    ],
    [highlightedId]
  );

  const handleCy = useCallback((cy: Core) => {
    cy.off('tap', 'node');
    cy.on('tap', 'node', (evt) => {
      const n = evt.target;
      onNodeClickRef.current?.({ id: n.id(), label: n.data('label'), type: n.data('type') });
    });
  }, []);

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: '100%', height: '100%' }}
      layout={{ name: 'cose' }}
      stylesheet={stylesheet}
      minZoom={0.2}
      maxZoom={3}
      cy={handleCy}
    />
  );
}
