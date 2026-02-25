import { render, screen } from '@testing-library/react';
import { MarketShareChart } from '@/components/MarketShareChart';
import type { MarketShareEntry } from '@/types/api';

const sampleData: MarketShareEntry[] = [
  { canonical_name: 'Acme Corp', award_count: 10, total_obligated: 5_000_000, market_share_pct: 25 },
  { canonical_name: 'Beta LLC', award_count: 5, total_obligated: 2_500_000, market_share_pct: 12.5 },
];

describe('MarketShareChart', () => {
  it('renders without crashing with data', () => {
    const { container } = render(<MarketShareChart data={sampleData} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders without crashing with empty data', () => {
    const { container } = render(<MarketShareChart data={[]} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders a chart container element', () => {
    const { container } = render(<MarketShareChart data={sampleData} />);
    // ResponsiveContainer wraps in a div
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument();
  });
});
