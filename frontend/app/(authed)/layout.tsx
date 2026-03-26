'use client';
import { useEffect, useState } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { useRouter } from 'next/navigation';
import { Nav } from '@/components/Nav';
import { Footer } from '@/components/Footer';

export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    fetchAuthSession()
      .then((s) => {
        if (!s.tokens) router.replace('/login');
        else setReady(true);
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Nav />
      <main className="p-6 flex-1">{children}</main>
      <Footer />
    </div>
  );
}
