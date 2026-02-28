'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function AgenciesPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['agencies', page],
    queryFn: () => api.agencies.list(page),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Agencies</h1>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {isError && <p className="text-destructive">Failed to load agencies.</p>}
      {data && (
        <>
          <p className="text-sm text-muted-foreground">{data.total.toLocaleString()} agencies</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Agency Code</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <Link href={`/agencies/detail?id=${a.id}`} className="text-blue-600 hover:underline">
                      {a.agency_name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{a.agency_code ?? '—'}</TableCell>
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
