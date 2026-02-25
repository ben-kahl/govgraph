'use client';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    fetchAuthSession()
      .then((s) => { if (s.tokens) router.push('/dashboard'); })
      .catch(() => {});
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <Authenticator>
        {({ user }) => {
          if (user) router.push('/dashboard');
          return <></>;
        }}
      </Authenticator>
    </div>
  );
}
