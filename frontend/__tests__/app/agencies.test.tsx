import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AgenciesPage from '@/app/(authed)/agencies/page';
import type { PaginatedAgencies } from '@/types/api';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/lib/api', () => ({
  api: {
    agencies: {
      list: jest.fn(),
    },
  },
}));

const { api } = jest.requireMock('@/lib/api') as { api: { agencies: { list: jest.Mock } } };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const samplePage: PaginatedAgencies = {
  total: 15,
  page: 1,
  size: 20,
  items: [
    { id: 'a1', agency_name: 'Department of Defense', agency_code: 'DOD' },
    { id: 'a2', agency_name: 'Department of Energy', agency_code: null },
  ],
};

describe('AgenciesPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows loading state initially', () => {
    api.agencies.list.mockReturnValue(new Promise(() => {}));
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('shows agency names after data loads', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Department of Defense')).toBeInTheDocument();
      expect(screen.getByText('Department of Energy')).toBeInTheDocument();
    });
  });

  it('shows total agency count', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('15 agencies')).toBeInTheDocument();
    });
  });

  it('shows agency code in monospace column', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('DOD')).toBeInTheDocument();
    });
  });

  it('shows — for null agency_code', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('—')).toBeInTheDocument();
    });
  });

  it('shows error state on failure', async () => {
    api.agencies.list.mockRejectedValue(new Error('API error'));
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load agencies/i)).toBeInTheDocument();
    });
  });

  it('renders a search input and Search button', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    expect(screen.getByPlaceholderText('Search agencies…')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
  });

  it('submits search and refetches with query', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    const user = userEvent.setup();
    render(<AgenciesPage />, { wrapper: makeWrapper() });

    const input = screen.getByPlaceholderText('Search agencies…');
    await user.type(input, 'defense');
    await user.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(api.agencies.list).toHaveBeenCalledWith('defense', 1);
    });
  });

  it('disables Previous button on first page', async () => {
    api.agencies.list.mockResolvedValue(samplePage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    });
  });

  it('disables Next button when on last page', async () => {
    const lastPage: PaginatedAgencies = { ...samplePage, total: 2, size: 20 };
    api.agencies.list.mockResolvedValue(lastPage);
    render(<AgenciesPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    });
  });
});
