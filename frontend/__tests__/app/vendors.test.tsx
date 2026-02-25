import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import VendorsPage from '@/app/(authed)/vendors/page';
import type { PaginatedVendors } from '@/types/api';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/lib/api', () => ({
  api: {
    vendors: {
      list: jest.fn(),
    },
  },
}));

const { api } = jest.requireMock('@/lib/api') as { api: { vendors: { list: jest.Mock } } };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const samplePage: PaginatedVendors = {
  total: 42,
  page: 1,
  size: 20,
  items: [
    {
      id: 'v1',
      canonical_name: 'Acme Corp',
      uei: 'ACME123',
      duns: null,
      resolved_by_llm: false,
      resolution_confidence: 0.95,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    },
    {
      id: 'v2',
      canonical_name: 'Beta LLC',
      uei: null,
      duns: '987654321',
      resolved_by_llm: true,
      resolution_confidence: 0.72,
      created_at: '2024-01-02',
      updated_at: '2024-01-02',
    },
  ],
};

describe('VendorsPage', () => {
  beforeEach(() => jest.clearAllMocks());

  it('shows loading state initially', () => {
    api.vendors.list.mockReturnValue(new Promise(() => {}));
    render(<VendorsPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('shows vendor names after data loads', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      expect(screen.getByText('Beta LLC')).toBeInTheDocument();
    });
  });

  it('shows total vendor count', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText('42 vendors')).toBeInTheDocument();
    });
  });

  it('shows LLM badge for LLM-resolved vendors', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      // Beta LLC is resolved_by_llm: true
      expect(screen.getByText('LLM')).toBeInTheDocument();
    });
  });

  it('shows — for null UEI', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      // Beta LLC has uei: null
      expect(screen.getByText('—')).toBeInTheDocument();
    });
  });

  it('shows error state on failure', async () => {
    api.vendors.list.mockRejectedValue(new Error('API error'));
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load vendors/i)).toBeInTheDocument();
    });
  });

  it('submits search and refetches with query', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    const user = userEvent.setup();
    render(<VendorsPage />, { wrapper: makeWrapper() });

    const input = screen.getByPlaceholderText('Search vendors…');
    await user.type(input, 'acme');
    await user.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      // api.vendors.list should have been called at least twice:
      // once on mount (no query), once after search
      expect(api.vendors.list).toHaveBeenCalledWith('acme', 1);
    });
  });

  it('disables Previous button on first page', async () => {
    api.vendors.list.mockResolvedValue(samplePage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    });
  });

  it('disables Next button when on last page', async () => {
    const lastPage: PaginatedVendors = { ...samplePage, total: 2, size: 20 };
    api.vendors.list.mockResolvedValue(lastPage);
    render(<VendorsPage />, { wrapper: makeWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    });
  });
});
