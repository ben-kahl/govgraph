'use client';
import dynamic from 'next/dynamic';
import type { GraphNode, GraphEdge } from '@/types/api';

const CytoscapeComponent = dynamic(() => import('react-cytoscapejs'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      Loading graph…
    </div>
  ),
});

const stylesheet = [
  {
    selector: 'node[type="Vendor"]',
    style: { 'background-color': '#3b82f6', label: 'data(label)', 'font-size': '10px', color: '#fff', 'text-valign': 'center' as const, 'text-halign': 'center' as const },
  },
  {
    selector: 'node[type="Agency"]',
    style: { 'background-color': '#10b981', label: 'data(label)', 'font-size': '10px', color: '#fff', 'text-valign': 'center' as const, 'text-halign': 'center' as const },
  },
  {
    selector: 'node[type="Contract"]',
    style: { 'background-color': '#f59e0b', shape: 'rectangle' as const, label: 'data(label)', 'font-size': '9px', color: '#fff', 'text-valign': 'center' as const, 'text-halign': 'center' as const },
  },
  {
    selector: 'edge',
    style: {
      'line-color': '#94a3b8',
      'target-arrow-color': '#94a3b8',
      'target-arrow-shape': 'triangle' as const,
      'curve-style': 'bezier' as const,
      label: 'data(label)',
      'font-size': '8px',
    },
  },
];

export function CytoscapeGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const elements = [
    ...nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type } })),
    ...edges.map((e) => ({ data: { source: e.source, target: e.target, label: e.type } })),
  ];

  return (
    <CytoscapeComponent
      elements={elements}
      style={{ width: '100%', height: '100%' }}
      layout={{ name: 'cose' }}
      stylesheet={stylesheet}
      minZoom={0.2}
      maxZoom={3}
    />
  );
}
