import { render, screen } from '@testing-library/react';
import LandingPage from '@/app/page';

describe('LandingPage', () => {
  it('shows the GovGraph heading', () => {
    render(<LandingPage />);
    expect(screen.getByRole('heading', { name: 'GovGraph' })).toBeInTheDocument();
  });

  it('shows a description about federal contracts', () => {
    render(<LandingPage />);
    expect(screen.getByText(/federal government contracts/i)).toBeInTheDocument();
  });

  it('shows the Sign In call-to-action link', () => {
    render(<LandingPage />);
    const link = screen.getByRole('link', { name: /sign in/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/login');
  });

  it('lists all four feature bullet points', () => {
    render(<LandingPage />);
    expect(screen.getByText(/10,000\+ resolved vendor entities/i)).toBeInTheDocument();
    expect(screen.getByText(/interactive graph canvas/i)).toBeInTheDocument();
    expect(screen.getByText(/risk indicators/i)).toBeInTheDocument();
    expect(screen.getByText(/market-share/i)).toBeInTheDocument();
  });
});
