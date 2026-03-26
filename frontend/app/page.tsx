import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Footer } from '@/components/Footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col items-center justify-center gap-8 p-12 text-center">
        <div className="max-w-2xl space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">GovGraph</h1>
          <p className="text-xl text-muted-foreground">
            Explore the web of federal government contracts. Track vendor relationships,
            spot award anomalies, and visualize agency spending — powered by live USAspending data.
          </p>
          <ul className="text-left text-muted-foreground space-y-1 list-disc list-inside">
            <li>Search and filter 10,000+ resolved vendor entities</li>
            <li>Interactive graph canvas for vendor–agency–contract relationships</li>
            <li>Risk indicators: award spikes, new entrants, sole-source agencies</li>
            <li>Market-share and spending-over-time analytics</li>
          </ul>
        </div>
        <Button asChild size="lg">
          <Link href="/login">Sign In to Get Started</Link>
        </Button>
      </main>
      <Footer />
    </div>
  );
}
