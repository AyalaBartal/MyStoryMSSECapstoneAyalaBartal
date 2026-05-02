import { useEffect, useState } from "react";
import { useAuth } from "./useAuth";
import { apiCall } from "./api";

/**
 * Custom hook for loading the current parent's kids.
 *
 * Returns:
 *   - kids: array | null     (null while loading or anonymous)
 *   - isLoading: boolean
 *   - error: string | null
 *   - refresh(): re-fetch (e.g. after creating a kid in another tab)
 *
 * Anonymous users get { kids: null, isLoading: false, error: null }.
 * That's the signal to fall back to name/age inputs.
 */
export function useKids() {
  const { user, isLoading: authLoading } = useAuth();
  const [kids, setKids] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  async function refresh() {
    if (!user) {
      setKids(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiCall("GET", "/kids");
      setKids(data.kids || []);
    } catch (err) {
      setError(err.message);
      setKids([]);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading) return;
    refresh();
  }, [authLoading, user]);

  return { kids, isLoading, error, refresh };
}