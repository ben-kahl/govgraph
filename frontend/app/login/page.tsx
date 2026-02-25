'use client';
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';

const formFields = {
  signUp: {
    password: {
      label: 'Password',
      placeholder: 'Create your password',
      order: 1,
    },
    confirm_password: {
      label: 'Confirm Password',
      order: 2,
    },
  },
};

function PasswordHint() {
  const { route } = useAuthenticator((ctx) => [ctx.route]);
  if (route !== 'signUp') return null;
  return (
    <p className="text-xs text-gray-500 px-1 -mt-2">
      Must be at least 12 characters and include uppercase, lowercase, number, and symbol.
    </p>
  );
}

const components = {
  SignUp: {
    FormFields() {
      return (
        <>
          <Authenticator.SignUp.FormFields />
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '-0.5rem', padding: '0 4px' }}>
            Must be at least 12 characters and include uppercase, lowercase, number, and symbol.
          </p>
        </>
      );
    },
  },
};

function RedirectWhenAuthenticated() {
  const router = useRouter();
  const { authStatus } = useAuthenticator((ctx) => [ctx.authStatus]);
  useEffect(() => {
    if (authStatus === 'authenticated') router.push('/dashboard');
  }, [authStatus, router]);
  return null;
}

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    fetchAuthSession()
      .then((s) => { if (s.tokens) router.push('/dashboard'); })
      .catch(() => {});
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <Authenticator
        socialProviders={['google']}
        formFields={formFields}
        components={components}
      >
        <RedirectWhenAuthenticated />
      </Authenticator>
    </div>
  );
}
