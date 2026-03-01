import { render, screen } from '@testing-library/react';
import type { GraphNode, GraphEdge } from '@/types/api';

// Mock react-cytoscapejs before importing CytoscapeGraph
jest.mock('react-cytoscapejs', () => ({
  __esModule: true,
  default: ({ elements }: { elements: unknown[] }) => (
    <div data-testid="cytoscape-canvas" data-element-count={elements.length} />
  ),
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
jest.mock('next/dynamic', () => (fn: () => Promise<{ default: unknown }>) => {
  // Resolve the dynamic import synchronously in tests
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require('react-cytoscapejs').default;
});

import { CytoscapeGraph } from '@/components/CytoscapeGraph';

const nodes: GraphNode[] = [
  { data: { id: 'v1', label: 'Acme Corp', type: 'Vendor' } },
  { data: { id: 'a1', label: 'DoD', type: 'Agency' } },
  { data: { id: 'c1', label: 'Contract-001', type: 'Contract' } },
];

const edges: GraphEdge[] = [
  { data: { id: 'e1', source: 'v1', target: 'c1', label: 'AWARDED_CONTRACT' } },
  { data: { id: 'e2', source: 'a1', target: 'c1', label: 'ISSUED_CONTRACT' } },
];

describe('CytoscapeGraph', () => {
  it('renders the cytoscape canvas', () => {
    render(<CytoscapeGraph nodes={nodes} edges={edges} />);
    expect(screen.getByTestId('cytoscape-canvas')).toBeInTheDocument();
  });

  it('passes combined element count (nodes + edges) to Cytoscape', () => {
    render(<CytoscapeGraph nodes={nodes} edges={edges} />);
    const canvas = screen.getByTestId('cytoscape-canvas');
    expect(canvas).toHaveAttribute('data-element-count', String(nodes.length + edges.length));
  });

  it('renders with empty nodes and edges', () => {
    render(<CytoscapeGraph nodes={[]} edges={[]} />);
    const canvas = screen.getByTestId('cytoscape-canvas');
    expect(canvas).toHaveAttribute('data-element-count', '0');
  });

  it('renders with only nodes and no edges', () => {
    render(<CytoscapeGraph nodes={nodes} edges={[]} />);
    const canvas = screen.getByTestId('cytoscape-canvas');
    expect(canvas).toHaveAttribute('data-element-count', String(nodes.length));
  });
});
