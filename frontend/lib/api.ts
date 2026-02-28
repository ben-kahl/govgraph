import { fetchAuthSession } from 'aws-amplify/auth';
import type {
  PaginatedVendors,
  Vendor,
  PaginatedAgencies,
  Agency,
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
    list: (q?: string, page = 1, size = 20) =>
      apiFetch<PaginatedVendors>(
        `/vendors?page=${page}&size=${size}${q ? `&q=${encodeURIComponent(q)}` : ''}`
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
    marketShare: (limit = 25) =>
      apiFetch<MarketShareEntry[]>(`/analytics/market-share?limit=${limit}`),
    spendingOverTime: (agencyId: string, period = 'month') =>
      apiFetch<SpendingTimeSeries[]>(
        `/analytics/agency/${agencyId}/spending-over-time?period=${period}`
      ),
    awardSpikes: (z = 3) =>
      apiFetch<AnomalyEntry[]>(`/analytics/risk/award-spikes?z_threshold=${z}`),
    newEntrants: (days = 90) =>
      apiFetch<NewEntrant[]>(`/analytics/risk/new-entrants?days=${days}`),
    soleSource: () => apiFetch<SoleSourceFlag[]>('/analytics/risk/sole-source'),
  },
  graph: {
    vendor: (id: string) => apiFetch<GraphResponse>(`/graph/vendor/${id}`),
    agency: (id: string) => apiFetch<GraphResponse>(`/graph/agency/${id}`),
    path: (from: string, to: string) =>
      apiFetch<GraphResponse>(`/graph/path?from=${from}&to=${to}`),
  },
};
