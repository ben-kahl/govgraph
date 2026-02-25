import { Amplify } from 'aws-amplify';

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID!,
      userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID!,
      loginWith: {
        email: true,
        oauth: {
          domain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN!,
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [`${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}/login`],
          redirectSignOut: [process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'],
          responseType: 'code',
        },
      },
    },
  },
});
