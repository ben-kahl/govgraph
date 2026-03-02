import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import DashboardPage from '@/app/(authed)/dashboard/page';
import type { MarketShareEntry, AgencyMarketShareEntry, SummaryStats } from '@/types/api';

// Mock recharts to avoid canvas/resize issues in jsdom
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

jest.mock('@/lib/api', () => ({
  api: {
    analytics: {
      marketShare: jest.fn(),
      agencyMarketShare: jest.fn(),
      summary: jest.fn(),
    },
    vendors: { list: jest.fn() },
    agencies: { list: jest.fn() },
  },
}));

const { api } = jest.requireMock('@/lib/api') as {
  api: {
    analytics: {
      marketShare: jest.Mock;
      agencyMarketShare: jest.Mock;
      summary: jest.Mock;
    };
    vendors: { list: jest.Mock };
    agencies: { list: jest.Mock };
  };
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const sampleVendorData: MarketShareEntry[] = [
  { canonical_name: 'Acme Corp', award_count: 10, total_obligated: 5_000_000, market_share_pct: 25 },
];

const sampleAgencyData: AgencyMarketShareEntry[] = [
  { agency_name: 'Dept of Defense', award_count: 50, total_obligated: 20_000_000, market_share_pct: 40 },
];

const sampleSummary: SummaryStats = {
  total_vendors: 1200,
  total_agencies: 85,
  total_contracts: 45000,
  total_obligated_amount: 500_000_000,
};

function mockAllPending() {
  api.analytics.marketShare.mockReturnValue(new Promise(() => {}));
  api.analytics.agencyMarketShare.mockReturnValue(new Promise(() => {}));
  api.analytics.summary.mockReturnValue(new Promise(() => {}));
}

function mockAllResolved() {
  api.analytics.marketShare.mockResolvedValue(sampleVendorData);
  api.analytics.agencyMarketShare.mockResolvedValue(sampleAgencyData);
  api.analytics.summary.mockResolvedValue(sampleSummary);
}

describe('DashboardPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows loading states while data is fetching', () => {
    mockAllPending();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getAllByText('Loading…').length).toBeGreaterThanOrEqual(1);
  });

  it('renders both charts after data loads', async () => {
    mockAllResolved();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
    });
    expect(screen.getAllByTestId('bar-chart').length).toBe(2);
  });

  it('shows an error message when market share fetch fails', async () => {
    api.analytics.marketShare.mockRejectedValue(new Error('Network error'));
    api.analytics.agencyMarketShare.mockReturnValue(new Promise(() => {}));
    api.analytics.summary.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load market share/i)).toBeInTheDocument();
    });
  });

  it('renders the page heading', () => {
    mockAllPending();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });

  it('renders both chart card titles', () => {
    mockAllPending();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Top Vendors by Contract Value')).toBeInTheDocument();
    expect(screen.getByText('Top Agencies by Award Volume')).toBeInTheDocument();
  });

  it('renders KPI card titles', () => {
    mockAllPending();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Total Contracts')).toBeInTheDocument();
    expect(screen.getByText('Total Vendors')).toBeInTheDocument();
    expect(screen.getByText('Total Obligated')).toBeInTheDocument();
    expect(screen.getByText('Agencies')).toBeInTheDocument();
  });

  it('populates KPI cards after summary loads', async () => {
    mockAllResolved();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('45,000')).toBeInTheDocument();
      expect(screen.getByText('1,200')).toBeInTheDocument();
      expect(screen.getByText('85')).toBeInTheDocument();
    });
  });

  it('renders the search bar', () => {
    mockAllPending();
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByPlaceholderText('Search vendors or agencies…')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('fires vendor and agency searches on submit', async () => {
    mockAllPending();
    api.vendors.list.mockResolvedValue({ items: [], total: 0, page: 1, size: 5 });
    api.agencies.list.mockResolvedValue({ items: [], total: 0, page: 1, size: 5 });
    render(<DashboardPage />, { wrapper: makeWrapper() });

    const input = screen.getByPlaceholderText('Search vendors or agencies…');
    await userEvent.type(input, 'boeing');
    await userEvent.click(screen.getByRole('button', { name: /search/i }));

    await waitFor(() => {
      expect(api.vendors.list).toHaveBeenCalledWith('boeing', 1, 5);
      expect(api.agencies.list).toHaveBeenCalledWith('boeing', 1, 5);
    });
  });
});
