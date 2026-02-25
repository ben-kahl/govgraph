'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function VendorsPage() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['vendors', query, page],
    queryFn: () => api.vendors.list(query || undefined, page),
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(search);
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
                <TableHead>Name</TableHead>
                <TableHead>UEI</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>LLM Resolved</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>
                    <Link href={`/vendors/${v.id}`} className="text-blue-600 hover:underline">
                      {v.canonical_name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{v.uei ?? '—'}</TableCell>
                  <TableCell>{(v.resolution_confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>
                    {v.resolved_by_llm && <Badge variant="secondary">LLM</Badge>}
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
