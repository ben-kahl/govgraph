import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import DashboardPage from '@/app/(authed)/dashboard/page';
import type { MarketShareEntry } from '@/types/api';

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
    },
  },
}));

const { api } = jest.requireMock('@/lib/api') as { api: { analytics: { marketShare: jest.Mock } } };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const sampleData: MarketShareEntry[] = [
  { canonical_name: 'Acme Corp', award_count: 10, total_obligated: 5_000_000, market_share_pct: 25 },
];

describe('DashboardPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows a loading state while data is fetching', () => {
    api.analytics.marketShare.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders the market share chart after data loads', async () => {
    api.analytics.marketShare.mockResolvedValue(sampleData);
    render(<DashboardPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('shows an error message when fetch fails', async () => {
    api.analytics.marketShare.mockRejectedValue(new Error('Network error'));
    render(<DashboardPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load market share/i)).toBeInTheDocument();
    });
  });

  it('renders the page heading', () => {
    api.analytics.marketShare.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });

  it('renders the card title', () => {
    api.analytics.marketShare.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Top Vendors by Contract Value')).toBeInTheDocument();
  });
});
