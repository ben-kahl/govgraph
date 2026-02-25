import { render } from '@testing-library/react';
import { SpendingChart } from '@/components/SpendingChart';
import type { SpendingTimeSeries } from '@/types/api';

const sampleData: SpendingTimeSeries[] = [
  { period: '2024-01', contract_count: 12, total_obligated: 3_000_000 },
  { period: '2024-02', contract_count: 8, total_obligated: 1_500_000 },
  { period: '2024-03', contract_count: 15, total_obligated: 4_200_000 },
];

describe('SpendingChart', () => {
  it('renders without crashing with data', () => {
    const { container } = render(<SpendingChart data={sampleData} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders without crashing with empty data', () => {
    const { container } = render(<SpendingChart data={[]} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders a chart container element', () => {
    const { container } = render(<SpendingChart data={sampleData} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument();
  });
});
