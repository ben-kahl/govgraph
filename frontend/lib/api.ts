import { fetchAuthSession } from 'aws-amplify/auth';
import type {
  PaginatedVendors,
  Vendor,
  PaginatedAgencies,
  Agency,
  SummaryStats,
  AgencyMarketShareEntry,
  MarketShareEntry,
  SpendingTimeSeries,
  AnomalyEntry,
  NewEntrant,
  SoleSourceFlag,
  GraphResponse,
  HubVendor,
} from '@/types/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = await fetchAuthSession();
  const token = session.tokens?.accessToken?.toString();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json();
}

export const api = {
  vendors: {
    list: (q?: string, page = 1, size = 20, sortBy = 'total_obligated', sortDir = 'desc') =>
      apiFetch<PaginatedVendors>(
        `/vendors?page=${page}&size=${size}&sort_by=${sortBy}&sort_dir=${sortDir}${q ? `&q=${encodeURIComponent(q)}` : ''}`
      ),
    getById: (id: string) => apiFetch<Vendor>(`/vendors/${id}`),
  },
  agencies: {
    list: (q?: string, page = 1, size = 20) =>
      apiFetch<PaginatedAgencies>(
        `/agencies?page=${page}&size=${size}${q ? `&q=${encodeURIComponent(q)}` : ''}`
      ),
    getById: (id: string) => apiFetch<Agency>(`/agencies/${id}`),
  },
  analytics: {
    summary: () => apiFetch<SummaryStats>('/insights/summary'),
    marketShare: (limit = 25) =>
      apiFetch<MarketShareEntry[]>(`/insights/market-share?limit=${limit}`),
    agencyMarketShare: (limit = 10) =>
      apiFetch<AgencyMarketShareEntry[]>(`/insights/agency-market-share?limit=${limit}`),
    spendingOverTime: (agencyId: string, period = 'month') =>
      apiFetch<SpendingTimeSeries[]>(
        `/insights/agency/${agencyId}/spending-over-time?period=${period}`
      ),
    awardSpikes: (z = 3) =>
      apiFetch<AnomalyEntry[]>(`/insights/risk/award-spikes?z_threshold=${z}`),
    newEntrants: (days = 90) =>
      apiFetch<NewEntrant[]>(`/insights/risk/new-entrants?days=${days}`),
    soleSource: () => apiFetch<SoleSourceFlag[]>('/insights/risk/sole-source'),
  },
  graph: {
    vendor: (id: string, limit = 500) =>
      apiFetch<GraphResponse>(`/graph/vendor/${id}?limit=${limit}`),
    agency: (id: string, limit = 1000) =>
      apiFetch<GraphResponse>(`/graph/agency/${id}?limit=${limit}`),
    overview: (limit = 30) => apiFetch<GraphResponse>(`/graph/overview?limit=${limit}`),
    explore: () => apiFetch<GraphResponse>('/graph/explore'),
    path: (from: string, to: string) =>
      apiFetch<GraphResponse>(`/graph/path?from=${from}&to=${to}`),
  },
};
