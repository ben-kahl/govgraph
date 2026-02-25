import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import RiskPage from '@/app/(authed)/risk/page';
import type { AnomalyEntry, NewEntrant, SoleSourceFlag } from '@/types/api';

jest.mock('@/lib/api', () => ({
  api: {
    analytics: {
      awardSpikes: jest.fn(),
      newEntrants: jest.fn(),
      soleSource: jest.fn(),
    },
  },
}));

const { api } = jest.requireMock('@/lib/api') as {
  api: {
    analytics: {
      awardSpikes: jest.Mock;
      newEntrants: jest.Mock;
      soleSource: jest.Mock;
    };
  };
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const sampleSpikes: AnomalyEntry[] = [
  {
    canonical_name: 'Acme Corp',
    contract_id: 'C001',
    obligated_amount: 9_000_000,
    avg_amount: 1_000_000,
    z_score: 4.2,
  },
];

const sampleEntrants: NewEntrant[] = [
  {
    canonical_name: 'NewCo Inc',
    first_award: '2024-01-15',
    award_count: 3,
    total_value: 750_000,
  },
];

const sampleSoleSource: SoleSourceFlag[] = [
  {
    agency_name: 'NASA',
    sole_vendor: 'SpaceTech Ltd',
    contracts: 8,
    total_spend: 12_000_000,
  },
];

describe('RiskPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders the Risk Indicators heading', () => {
    api.analytics.awardSpikes.mockReturnValue(new Promise(() => {}));
    api.analytics.newEntrants.mockReturnValue(new Promise(() => {}));
    api.analytics.soleSource.mockReturnValue(new Promise(() => {}));
    render(<RiskPage />, { wrapper: makeWrapper() });
    expect(screen.getByRole('heading', { name: /risk indicators/i })).toBeInTheDocument();
  });

  it('renders all three section headings', () => {
    api.analytics.awardSpikes.mockReturnValue(new Promise(() => {}));
    api.analytics.newEntrants.mockReturnValue(new Promise(() => {}));
    api.analytics.soleSource.mockReturnValue(new Promise(() => {}));
    render(<RiskPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Award Spikes')).toBeInTheDocument();
    expect(screen.getByText('New Entrants (last 90 days)')).toBeInTheDocument();
    expect(screen.getByText('Sole-Source Agencies')).toBeInTheDocument();
  });

  it('shows "No anomalies detected" when award spikes is empty', async () => {
    api.analytics.awardSpikes.mockResolvedValue([]);
    api.analytics.newEntrants.mockResolvedValue([]);
    api.analytics.soleSource.mockResolvedValue([]);
    render(<RiskPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('No anomalies detected.')).toBeInTheDocument();
    });
  });

  it('shows "No new entrants" when new entrants is empty', async () => {
    api.analytics.awardSpikes.mockResolvedValue([]);
    api.analytics.newEntrants.mockResolvedValue([]);
    api.analytics.soleSource.mockResolvedValue([]);
    render(<RiskPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('No new entrants.')).toBeInTheDocument();
    });
  });

  it('shows award spike data rows', async () => {
    api.analytics.awardSpikes.mockResolvedValue(sampleSpikes);
    api.analytics.newEntrants.mockResolvedValue([]);
    api.analytics.soleSource.mockResolvedValue([]);
    render(<RiskPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      expect(screen.getByText('C001')).toBeInTheDocument();
      expect(screen.getByText('4.20')).toBeInTheDocument();
    });
  });

  it('shows new entrant data rows', async () => {
    api.analytics.awardSpikes.mockResolvedValue([]);
    api.analytics.newEntrants.mockResolvedValue(sampleEntrants);
    api.analytics.soleSource.mockResolvedValue([]);
    render(<RiskPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('NewCo Inc')).toBeInTheDocument();
      expect(screen.getByText('2024-01-15')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('shows sole-source data rows', async () => {
    api.analytics.awardSpikes.mockResolvedValue([]);
    api.analytics.newEntrants.mockResolvedValue([]);
    api.analytics.soleSource.mockResolvedValue(sampleSoleSource);
    render(<RiskPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('NASA')).toBeInTheDocument();
      expect(screen.getByText('SpaceTech Ltd')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });
  });
});
