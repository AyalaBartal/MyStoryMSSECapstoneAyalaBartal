import { Link } from "react-router-dom";
import { useAuth } from "./useAuth";

/**
 * Top-of-app header. Shows different actions based on auth state.
 *
 * Anonymous: just a "Sign in to save" button.
 * Signed in: avatar + email + nav links + Sign out.
 */
export function Header({ openAuthModal }) {
  const { user, signOut } = useAuth();

  if (!user) {
    return (
      <div className="auth-header">
        <button className="auth-btn primary" onClick={openAuthModal}>
          Sign in to save
        </button>
      </div>
    );
  }

  const initial = (user.email?.[0] || "?").toUpperCase();

  return (
    <div className="auth-header">
      <div className="auth-avatar" aria-hidden="true">
        {initial}
      </div>
      <span className="auth-email">{user.email}</span>
      <Link to="/library" className="auth-link">
        My Library
      </Link>
      <Link to="/family" className="auth-link">
        My Family
      </Link>
      <button className="auth-btn" onClick={signOut} title="Sign out">
        Sign out
      </button>
    </div>
  );
}