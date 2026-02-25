import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
  usePathname: jest.fn(),
}));

jest.mock('aws-amplify/auth', () => ({
  signOut: jest.fn(),
}));

import { Nav } from '@/components/Nav';
import { useRouter, usePathname } from 'next/navigation';
import { signOut } from 'aws-amplify/auth';

const mockPush = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
  (usePathname as jest.Mock).mockReturnValue('/dashboard');
  (signOut as jest.Mock).mockResolvedValue(undefined);
});

describe('Nav', () => {
  it('renders the GovGraph brand link', () => {
    render(<Nav />);
    expect(screen.getByRole('link', { name: 'GovGraph' })).toBeInTheDocument();
  });

  it('renders all five nav links', () => {
    render(<Nav />);
    ['Dashboard', 'Vendors', 'Agencies', 'Graph', 'Risk'].forEach((label) => {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
    });
  });

  it('nav links point to the correct hrefs', () => {
    render(<Nav />);
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard');
    expect(screen.getByRole('link', { name: 'Vendors' })).toHaveAttribute('href', '/vendors');
    expect(screen.getByRole('link', { name: 'Agencies' })).toHaveAttribute('href', '/agencies');
    expect(screen.getByRole('link', { name: 'Graph' })).toHaveAttribute('href', '/graph');
    expect(screen.getByRole('link', { name: 'Risk' })).toHaveAttribute('href', '/risk');
  });

  it('renders a Sign Out button', () => {
    render(<Nav />);
    expect(screen.getByRole('button', { name: 'Sign Out' })).toBeInTheDocument();
  });

  it('calls signOut and navigates to / when Sign Out is clicked', async () => {
    const user = userEvent.setup();
    render(<Nav />);
    await user.click(screen.getByRole('button', { name: 'Sign Out' }));
    await waitFor(() => {
      expect(signOut).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });
});
