import { useEffect, useState } from "react";
import {
  fetchAuthSession,
  getCurrentUser,
  signOut as amplifySignOut,
} from "aws-amplify/auth";
import { Hub } from "aws-amplify/utils";

/**
 * Custom React hook for auth state.
 *
 * Returns:
 *   - user: { username, email } | null
 *   - idToken: string | null  (the JWT to send to the backend)
 *   - isLoading: boolean      (true while initial auth check runs)
 *   - signOut(): Promise<void>
 *
 * Listens to Amplify's auth event hub so when the user signs in via
 * the Authenticator modal, every component using this hook updates.
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [idToken, setIdToken] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  async function refresh() {
    try {
      const currentUser = await getCurrentUser();
      const session = await fetchAuthSession();
      setUser({
        username: currentUser.username,
        email: currentUser.signInDetails?.loginId || currentUser.username,
      });
      setIdToken(session.tokens?.idToken?.toString() ?? null);
    } catch {
      // No signed-in user — anonymous mode.
      setUser(null);
      setIdToken(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();

    // Re-check auth state on Amplify auth events.
    const unsubscribe = Hub.listen("auth", (data) => {
      const event = data.payload.event;
      if (event === "signedIn" || event === "signedOut" || event === "tokenRefresh") {
        refresh();
      }
    });

    return unsubscribe;
  }, []);

  async function signOut() {
    await amplifySignOut();
    // Hub will fire signedOut → refresh()
  }

  return { user, idToken, isLoading, signOut };
}