import { fetchAuthSession } from "aws-amplify/auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

/**
 * Make an API call to the My Story backend.
 * Auto-attaches the Cognito ID token if the user is signed in.
 * Anonymous (no token) requests still work for endpoints that allow it.
 */
export async function apiCall(method, path, body) {
  const headers = { "Content-Type": "application/json" };

  // Attach JWT if we have one. fetchAuthSession is cheap when cached,
  // and silently returns no tokens for anonymous users.
  try {
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  } catch {
    // Anonymous — no token, no header. Backend handles this.
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(
      errorBody.error || `${method} ${path} failed with ${res.status}`,
    );
  }

  // 204 No Content → no body to parse
  if (res.status === 204) return null;
  return res.json();
}