import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import GraphPage from '@/app/(authed)/graph/page';
import type { ClickedNode } from '@/components/CytoscapeGraph';
import type { PaginatedVendors, PaginatedAgencies, GraphResponse } from '@/types/api';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/lib/api', () => ({
  api: {
    vendors: { list: jest.fn() },
    agencies: { list: jest.fn() },
    graph: { vendor: jest.fn(), agency: jest.fn(), overview: jest.fn(), explore: jest.fn() },
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
    // Clicking the outer div fires a Contract node click (preserves existing tests).
    // The inner buttons fire Vendor/Agency clicks with stopPropagation so they
    // don't also trigger the Contract click.
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
    >
      <button
        data-testid="click-vendor-node"
        onClick={(e) => {
          e.stopPropagation();
          onNodeClick?.({ id: 'v1', label: 'Palantir Technologies', type: 'Vendor' });
        }}
      />
      <button
        data-testid="click-agency-node"
        onClick={(e) => {
          e.stopPropagation();
          onNodeClick?.({ id: 'a1', label: 'DoD', type: 'Agency' });
        }}
      />
    </div>
  ),
}));

const { api } = jest.requireMock('@/lib/api') as {
  api: {
    vendors: { list: jest.Mock };
    agencies: { list: jest.Mock };
    graph: { vendor: jest.Mock; agency: jest.Mock; overview: jest.Mock; explore: jest.Mock };
  };
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const sampleAgencies: PaginatedAgencies = {
  total: 1,
  page: 1,
  size: 8,
  items: [{ id: 'a1', agency_name: 'DoD', agency_code: 'DOD' }],
};

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

  it('renders Vendor, Agency and Overview toggle buttons', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole('button', { name: 'Vendor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agency' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Overview' })).toBeInTheDocument();
  });

  it('renders search input with vendor placeholder by default', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(screen.getByPlaceholderText('Search vendors…')).toBeInTheDocument();
  });

  it('shows empty-state prompt before any selection', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    expect(
      screen.getByText('Search for a vendor or agency to explore the graph.')
    ).toBeInTheDocument();
  });

  it('renders layout selector with fcose as default', () => {
    render(<GraphPage />, { wrapper: makeWrapper() });
    const select = screen.getByRole('combobox');
    expect(select).toHaveValue('fcose');
  });

  it('shows dropdown suggestions when typing ≥2 chars', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => expect(screen.getByText('Palantir Technologies')).toBeInTheDocument());
  });

  it('adds entity to loaded list and triggers graph query', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => expect(screen.getByTestId('cytoscape-canvas')).toBeInTheDocument());
    expect(api.graph.vendor).toHaveBeenCalledWith('v1');
    // Entity appears in the loaded chip list
    expect(screen.getByText('Loaded (1)')).toBeInTheDocument();
  });

  it('shows legend with Contract type after graph loads', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));

    await waitFor(() => expect(screen.getByText('Contract')).toBeInTheDocument());
  });

  it('switches to agency search when Agency button is clicked', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Agency' }));
    expect(screen.getByPlaceholderText('Search agencies…')).toBeInTheDocument();
  });

  it('shows Load market overview button in Overview mode', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Overview' }));
    expect(screen.getByRole('button', { name: 'Load market overview' })).toBeInTheDocument();
  });

  it('calls api.graph.overview when Load market overview is clicked', async () => {
    api.graph.overview.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Overview' }));
    await user.click(screen.getByRole('button', { name: 'Load market overview' }));

    await waitFor(() => expect(api.graph.overview).toHaveBeenCalled());
  });

  it('clicking a contract node shows obligated amount', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));
    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('cytoscape-canvas'));

    await waitFor(() => expect(screen.getByText('$450K')).toBeInTheDocument());
  });

  it('shows awarding agency for contract node from edge data', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));
    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('cytoscape-canvas'));

    await waitFor(() => expect(screen.getByText('DoD')).toBeInTheDocument());
  });

  it('vendor node shows "View detail" link pointing to /vendors/detail', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));
    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('click-vendor-node'));

    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'View detail →' });
      expect(link).toHaveAttribute('href', '/vendors/detail?id=v1');
    });
  });

  it('shows Explore button and calls api.graph.explore when clicked', async () => {
    api.graph.explore.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Explore' }));
    expect(screen.getByRole('button', { name: 'Explore dataset' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Explore dataset' }));

    await waitFor(() => expect(api.graph.explore).toHaveBeenCalled());
  });

  it('date filter hides contract nodes with signedDate before dateFrom', async () => {
    api.vendors.list.mockResolvedValue(sampleVendors);
    // sampleGraph has c1 with signedDate '2024-03-15'
    api.graph.vendor.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.type(screen.getByPlaceholderText('Search vendors…'), 'pal');
    await waitFor(() => screen.getByText('Palantir Technologies'));
    await user.click(screen.getByText('Palantir Technologies'));
    await waitFor(() => screen.getByTestId('cytoscape-canvas'));

    // All 3 nodes visible initially
    expect(screen.getByTestId('cytoscape-canvas')).toHaveAttribute('data-nodes', '3');

    // Filter: from 2025-01-01 — c1's signedDate (2024-03-15) is before this
    fireEvent.change(screen.getByLabelText('Date from'), { target: { value: '2025-01-01' } });

    // c1 filtered out → 2 nodes (v1, a1), 0 edges (both connected to c1)
    await waitFor(() => {
      expect(screen.getByTestId('cytoscape-canvas')).toHaveAttribute('data-nodes', '2');
      expect(screen.getByTestId('cytoscape-canvas')).toHaveAttribute('data-edges', '0');
    });
  });

  it('agency dropdown shows agency code in parentheses', async () => {
    api.agencies.list.mockResolvedValue(sampleAgencies);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Agency' }));
    await user.type(screen.getByPlaceholderText('Search agencies…'), 'dod');
    await waitFor(() => expect(screen.getByText('DoD (DOD)')).toBeInTheDocument());
  });

  it('agency dropdown omits parentheses when agency_code is null', async () => {
    const noCode: PaginatedAgencies = {
      total: 1, page: 1, size: 8,
      items: [{ id: 'a2', agency_name: 'Unknown Agency', agency_code: null }],
    };
    api.agencies.list.mockResolvedValue(noCode);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Agency' }));
    await user.type(screen.getByPlaceholderText('Search agencies…'), 'unk');
    await waitFor(() => expect(screen.getByText('Unknown Agency')).toBeInTheDocument());
    expect(screen.queryByText(/Unknown Agency \(/)).not.toBeInTheDocument();
  });

  it('agency node shows "View detail" link pointing to /agencies/detail', async () => {
    api.agencies.list.mockResolvedValue(sampleAgencies);
    api.graph.agency.mockResolvedValue(sampleGraph);
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: makeWrapper() });

    await user.click(screen.getByRole('button', { name: 'Agency' }));
    await user.type(screen.getByPlaceholderText('Search agencies…'), 'dod');
    await waitFor(() => screen.getByText('DoD (DOD)'));
    await user.click(screen.getByText('DoD (DOD)'));
    await waitFor(() => screen.getByTestId('cytoscape-canvas'));
    await user.click(screen.getByTestId('click-agency-node'));

    await waitFor(() => {
      const link = screen.getByRole('link', { name: 'View detail →' });
      expect(link).toHaveAttribute('href', '/agencies/detail?id=a1');
    });
  });
});
