import { api } from '@/lib/api';

// Must be before any import that triggers aws-amplify/auth
jest.mock('aws-amplify/auth', () => ({
  fetchAuthSession: jest.fn(),
}));

const { fetchAuthSession } = jest.requireMock('aws-amplify/auth') as {
  fetchAuthSession: jest.Mock;
};

const mockFetch = jest.fn();
global.fetch = mockFetch;

// Must match the value set in jest.setup.ts (read at module load time by api.ts)
const BASE_URL = 'https://api.test.example.com';

beforeEach(() => {
  fetchAuthSession.mockResolvedValue({
    tokens: { accessToken: { toString: () => 'test-access-token' } },
  });
});

afterEach(() => {
  jest.clearAllMocks();
});

function okJson(body: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
}

describe('apiFetch — Authorization header', () => {
  it('injects Bearer token from session', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 1, size: 20 }));
    await api.vendors.list();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-access-token' }),
      })
    );
  });

  it('throws when response is not ok', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve({}) });
    await expect(api.vendors.list()).rejects.toThrow('API 401');
  });
});

describe('api.vendors', () => {
  it('list() calls /vendors with default page and size', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 1, size: 20 }));
    await api.vendors.list();
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/vendors?page=1&size=20`,
      expect.any(Object)
    );
  });

  it('list() includes q param when query provided', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 1, size: 20 }));
    await api.vendors.list('acme corp');
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('q=acme%20corp');
  });

  it('list() omits q param when no query', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 1, size: 20 }));
    await api.vendors.list();
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).not.toContain('q=');
  });

  it('list() respects page and size args', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 3, size: 10 }));
    await api.vendors.list(undefined, 3, 10);
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/vendors?page=3&size=10`,
      expect.any(Object)
    );
  });

  it('getById() calls /vendors/:id', async () => {
    mockFetch.mockReturnValue(okJson({ id: 'v1', canonical_name: 'Acme' }));
    await api.vendors.getById('v1');
    expect(mockFetch).toHaveBeenCalledWith(`${BASE_URL}/vendors/v1`, expect.any(Object));
  });
});

describe('api.agencies', () => {
  it('list() calls /agencies', async () => {
    mockFetch.mockReturnValue(okJson({ items: [], total: 0, page: 1, size: 20 }));
    await api.agencies.list();
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/agencies?page=1&size=20`,
      expect.any(Object)
    );
  });

  it('getById() calls /agencies/:id', async () => {
    mockFetch.mockReturnValue(okJson({ id: 'a1', name: 'DoD' }));
    await api.agencies.getById('a1');
    expect(mockFetch).toHaveBeenCalledWith(`${BASE_URL}/agencies/a1`, expect.any(Object));
  });
});

describe('api.analytics', () => {
  it('marketShare() includes limit param', async () => {
    mockFetch.mockReturnValue(okJson([]));
    await api.analytics.marketShare(10);
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/analytics/market-share?limit=10`,
      expect.any(Object)
    );
  });

  it('spendingOverTime() builds correct URL', async () => {
    mockFetch.mockReturnValue(okJson([]));
    await api.analytics.spendingOverTime('a1', 'quarter');
    expect(mockFetch).toHaveBeenCalledWith(
      `${BASE_URL}/analytics/agency/a1/spending-over-time?period=quarter`,
      expect.any(Object)
    );
  });

  it('awardSpikes() includes z_threshold', async () => {
    mockFetch.mockReturnValue(okJson([]));
    await api.analytics.awardSpikes(2);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('z_threshold=2');
  });

  it('newEntrants() includes days param', async () => {
    mockFetch.mockReturnValue(okJson([]));
    await api.analytics.newEntrants(30);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('days=30');
  });
});

describe('api.graph', () => {
  it('vendor() calls /graph/vendor/:id', async () => {
    mockFetch.mockReturnValue(okJson({ nodes: [], edges: [] }));
    await api.graph.vendor('v1');
    expect(mockFetch).toHaveBeenCalledWith(`${BASE_URL}/graph/vendor/v1`, expect.any(Object));
  });

  it('path() encodes from and to', async () => {
    mockFetch.mockReturnValue(okJson({ nodes: [], edges: [] }));
    await api.graph.path('vendor-a', 'agency-b');
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('from=vendor-a');
    expect(url).toContain('to=agency-b');
  });
});
