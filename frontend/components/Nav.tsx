'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { signOut } from 'aws-amplify/auth';
import { Button } from '@/components/ui/button';

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/vendors', label: 'Vendors' },
  { href: '/agencies', label: 'Agencies' },
  { href: '/graph', label: 'Graph' },
  { href: '/risk', label: 'Risk' },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    await signOut();
    router.push('/');
  }

  return (
    <nav className="border-b bg-background px-6 py-3 flex items-center gap-6">
      <Link href="/dashboard" className="font-bold text-lg tracking-tight mr-4">
        GovGraph
      </Link>
      <div className="flex items-center gap-4 flex-1">
        {links.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`text-sm font-medium transition-colors hover:text-foreground/80 ${
              pathname === href ? 'text-foreground' : 'text-foreground/60'
            }`}
          >
            {label}
          </Link>
        ))}
      </div>
      <Button variant="outline" size="sm" onClick={handleSignOut}>
        Sign Out
      </Button>
    </nav>
  );
}
