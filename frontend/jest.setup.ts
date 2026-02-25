import '@testing-library/jest-dom';

// Env vars read at module load time — set before any test file imports them
process.env.NEXT_PUBLIC_API_URL = 'https://api.test.example.com';
process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID = 'us-east-1_TEST';
process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID = 'test-client-id';
process.env.NEXT_PUBLIC_COGNITO_REGION = 'us-east-1';
process.env.NEXT_PUBLIC_COGNITO_DOMAIN = 'test.auth.us-east-1.amazoncognito.com';
process.env.NEXT_PUBLIC_APP_URL = 'http://localhost:3000';

// Recharts uses ResizeObserver which is not available in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
