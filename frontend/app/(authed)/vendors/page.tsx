'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type SortCol = 'canonical_name' | 'contract_count' | 'total_obligated';
type SortDir = 'asc' | 'desc';

function SortIndicator({ col, sortBy, sortDir }: { col: SortCol; sortBy: SortCol; sortDir: SortDir }) {
  if (sortBy !== col) return <span className="ml-1 text-muted-foreground/40">↕</span>;
  return <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>;
}

export default function VendorsPage() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortCol>('total_obligated');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['vendors', query, page, sortBy, sortDir],
    queryFn: () => api.vendors.list(query || undefined, page, 20, sortBy, sortDir),
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(search);
    setPage(1);
  }

  function handleSort(col: SortCol) {
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      // Names default ascending; numeric columns default descending
      setSortDir(col === 'canonical_name' ? 'asc' : 'desc');
    }
    setPage(1);
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Vendors</h1>
      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <Input
          placeholder="Search vendors…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button type="submit">Search</Button>
      </form>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {isError && <p className="text-destructive">Failed to load vendors.</p>}
      {data && (
        <>
          <p className="text-sm text-muted-foreground">{data.total.toLocaleString()} vendors</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <button
                    onClick={() => handleSort('canonical_name')}
                    className="flex items-center hover:text-foreground"
                  >
                    Name <SortIndicator col="canonical_name" sortBy={sortBy} sortDir={sortDir} />
                  </button>
                </TableHead>
                <TableHead>UEI</TableHead>
                <TableHead className="text-right">
                  <button
                    onClick={() => handleSort('contract_count')}
                    className="flex items-center justify-end w-full hover:text-foreground"
                  >
                    Contracts <SortIndicator col="contract_count" sortBy={sortBy} sortDir={sortDir} />
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button
                    onClick={() => handleSort('total_obligated')}
                    className="flex items-center justify-end w-full hover:text-foreground"
                  >
                    Total Obligated <SortIndicator col="total_obligated" sortBy={sortBy} sortDir={sortDir} />
                  </button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>
                    <Link href={`/vendors/detail?id=${v.id}`} className="text-blue-600 hover:underline">
                      {v.canonical_name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{v.uei ?? '—'}</TableCell>
                  <TableCell className="text-right">{v.contract_count?.toLocaleString() ?? '—'}</TableCell>
                  <TableCell className="text-right">
                    {v.total_obligated != null
                      ? `$${(v.total_obligated / 1_000_000).toFixed(1)}M`
                      : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span className="text-sm self-center">Page {page}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={page * data.size >= data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
