import { render, screen, waitFor } from '@testing-library/react';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('@/components/Nav', () => ({
  Nav: () => <nav data-testid="nav">Nav</nav>,
}));

jest.mock('aws-amplify/auth', () => ({
  fetchAuthSession: jest.fn(),
}));

import AuthedLayout from '@/app/(authed)/layout';
import { useRouter } from 'next/navigation';
import { fetchAuthSession } from 'aws-amplify/auth';

const mockReplace = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  (useRouter as jest.Mock).mockReturnValue({ replace: mockReplace });
});

describe('AuthedLayout', () => {
  it('shows a loading state before session resolves', () => {
    (fetchAuthSession as jest.Mock).mockReturnValue(new Promise(() => {}));
    render(<AuthedLayout><div>Content</div></AuthedLayout>);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('redirects to /login when session has no tokens', async () => {
    (fetchAuthSession as jest.Mock).mockResolvedValue({ tokens: null });
    render(<AuthedLayout><div>Content</div></AuthedLayout>);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/login');
    });
  });

  it('redirects to /login when fetchAuthSession throws', async () => {
    (fetchAuthSession as jest.Mock).mockRejectedValue(new Error('Not authenticated'));
    render(<AuthedLayout><div>Content</div></AuthedLayout>);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/login');
    });
  });

  it('renders Nav and children when session has tokens', async () => {
    (fetchAuthSession as jest.Mock).mockResolvedValue({
      tokens: { accessToken: { toString: () => 'token' } },
    });
    render(<AuthedLayout><div data-testid="child">Page Content</div></AuthedLayout>);
    await waitFor(() => {
      expect(screen.getByTestId('nav')).toBeInTheDocument();
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });
  });

  it('does not redirect when session is valid', async () => {
    (fetchAuthSession as jest.Mock).mockResolvedValue({
      tokens: { accessToken: { toString: () => 'token' } },
    });
    render(<AuthedLayout><div>Content</div></AuthedLayout>);
    await waitFor(() => {
      expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
