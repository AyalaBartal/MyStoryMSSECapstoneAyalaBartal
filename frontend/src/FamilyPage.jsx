import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";

/**
 * My Family page — manage kid profiles.
 *
 * Auth-gated: anonymous users get redirected to "/" (story flow).
 * This handles two cases:
 *   1. User signs out while viewing /family → kicked back to home
 *   2. User opens /family directly without signing in → redirected
 *
 * Placeholder for Save B; will be built out next.
 */
export default function FamilyPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Wait for the initial auth check before redirecting — otherwise
    // we'd kick a signed-in user out during the brief moment when
    // useAuth is still resolving.
    if (!isLoading && !user) {
      navigate("/", { replace: true });
    }
  }, [isLoading, user, navigate]);

  // While auth resolves OR while redirect is in flight, render nothing
  // to avoid a flash of the family page for anonymous users.
  if (isLoading || !user) {
    return null;
  }

  return (
    <main className="app">
      <header>
        <h1>My Family</h1>
        <p className="subtitle">Manage your kids' profiles</p>
      </header>
      <div className="status-card">
        <p className="muted">Coming soon — kid profile manager goes here.</p>
        <Link to="/" className="primary-btn">
          ← Back to story
        </Link>
      </div>
    </main>
  );
}