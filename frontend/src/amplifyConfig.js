import { Amplify } from "aws-amplify";

// Configure Amplify once at module load. Vite injects these env vars
// at build time — they're public values (User Pool ID and App Client
// ID are designed to live in browser code).
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
      loginWith: {
        email: true,
      },
    },
  },
});