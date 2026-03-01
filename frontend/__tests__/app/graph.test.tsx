import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import GraphPage from '@/app/(authed)/graph/page';
import type { ClickedNode } from '@/components/CytoscapeGraph';
import type { PaginatedVendors, GraphResponse } from '@/types/api';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/lib/api', () => ({
  api: {
    vendors: { list: jest.fn() },
    agencies: { list: jest.fn() },
    graph: { vendor: jest.fn(), agency: jest.fn() },
  },
}));

jest.mock('@/components/CytoscapeGraph', () => ({
  CytoscapeGraph: ({
    nodes,
    edges,
    onNodeClick,
  }: {
    nodes: unknown[];
    edges: unknown[];
    onNodeClick?: (n: ClickedNode) => void;
  }) => (
    <div
      data-testid="cytoscape-canvas"
      data-nodes={nodes.length}
      data-edges={edges.length}
      onClick={() =>
        onNodeClick?.({
          id: 'c1',
          label: 'Provide IT services for the DoD',
          type: 'Contract',
          properties: {
            contractId: 'MSW25FR0001234',
            description: 'Provide IT services for the DoD',
            obligatedAmount: 450000,
            signedDate: '2024-03-15',
          },
        })
      }
    />
  ),
}));

const { api } = jest.requireMock('@/lib/api') as {
  api: {
    vendors: { list: jest.Mock };
    agencies: { list: jest.Mock };
    graph: { vendor: jest.Mock; agency: jest.Mock };
  };
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const sampleVendors: PaginatedVendors = {
  total: 1,
  page: 1,
  size: 8,
  items: [
    {
      id: 'v1',
      canonical_name: 'Palantir Technologies',
      uei: 'PAL123',
      duns: null,
      resolved_by_llm: false,
      resolution_confidence: 0.99,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    },
  ],
};

const sampleGraph: GraphResponse = {
  nodes: [
    { data: { id: 'v1', label: 'Palantir Technologies', type: 'Vendor' } },
    { data: { id: 'a1', label: 'DoD', type: 'Agency' } },
    {
      data: {
        id: 'c1',
        label: 'Provide IT services for the DoD',
        type: 'Contract',
        properties: {
          contractId: 'MSW25FR0001234',
          description: 'Provide IT services for the DoD',
          obligatedAmount: 450000,
          signedDate: '2024-03-15',
        },
      },
    },
  ],
  edges: [
    { data: { id: 'e1', source: 'v1', target: 'c1', label: 'AWARDED' } },
    { data: { id: 'e2', source: 'a1', target: 'c1', label: 'AWARDED_CONTRACT' } },
  ],
};

describe('GraphPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders Vendor and Agency toggle buttons', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole('button', { name: 'Vendor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agency' })).toBeInTheDocument();
  });

  it('renders search input with vendor placeholder by default', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(screen.getByPlaceholderText('Search vendors…')).toBeInTheDocument();
  });

  it('shows empty-state prompt before any search', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(
      screen.getByText('Search for a vendor or agency to explore the graph.')
    ).toBeInTheDocument();
  });

  it('renders layout selector with cose as default', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue('cose');
  });

  it('shows dropdown suggestions when typing ≥2 chars', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => {
      expect(screen.getByText('Palantir Technologies')).toBeInTheDocument();
    });
  });

  it('loads graph after clicking a suggestion', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => {
      expect(screen.getByTestId('cytoscape-canvas')).toBeInTheDocument();
    });
    expect(api.graph.vendor).toHaveBeenCalledWith('v1');
  });

  it('shows legend with Contract type after graph loads', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => {
      expect(screen.getByText('Contract')).toBeInTheDocument();
    });
  });

  it('switches to agency search when Agency button is clicked', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Agency' }));
    expect(screen.getByPlaceholderText('Search agencies…')).toBeInTheDocument();
  });

  it('clicking a contract node shows obligated amount and contract details', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('cytoscape-canvas'));

    await waitFor(() => {
      expect(screen.getByText('$450K')).toBeInTheDocument();
    });
  });

  it('shows vendor and awarding agency for contract node from edge data', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('cytoscape-canvas'));

    await waitFor(() => {
      // Palantir Technologies appears as both suggestion and vendor in panel
      expect(screen.getAllByText('Palantir Technologies').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('DoD')).toBeInTheDocument();
    });
  });
});
