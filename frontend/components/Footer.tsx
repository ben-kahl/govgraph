'use client';
import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function Footer() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <footer className="border-t bg-background px-6 py-4 flex items-center justify-between text-sm text-muted-foreground">
      <span>
        Built by{' '}
        <a
          href="https://linkedin.com/in/ben-kahl"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-foreground hover:underline"
        >
          Ben Kahl
        </a>
        {' '}·{' '}
        <a
          href="https://github.com/ben-kahl/govgraph"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          GitHub
        </a>
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
        aria-label="Toggle dark mode"
      >
        {resolvedTheme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>
    </footer>
  );
}
