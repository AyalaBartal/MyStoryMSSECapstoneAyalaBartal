import { useEffect, useState } from "react";
import { useAuth } from "./useAuth";
import { apiCall } from "./api";

/**
 * Custom hook for loading the current parent's stories.
 *
 * Args:
 *   - kidId: optional string to filter to one kid's stories
 *
 * Returns:
 *   - stories: array | null  (null while loading or anonymous)
 *   - isLoading: boolean
 *   - error: string | null
 *   - refresh(): re-fetch
 */
export function useStories(kidId) {
  const { user, isLoading: authLoading } = useAuth();
  const [stories, setStories] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  async function refresh() {
    if (!user) {
      setStories(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const path = kidId ? `/my-stories?kid_id=${encodeURIComponent(kidId)}` : "/my-stories";
      const data = await apiCall("GET", path);
      setStories(data.stories || []);
    } catch (err) {
      setError(err.message);
      setStories([]);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (authLoading) return;
    refresh();
  }, [authLoading, user, kidId]);

  return { stories, isLoading, error, refresh };
}