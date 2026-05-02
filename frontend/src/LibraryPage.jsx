import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";
import { useKids } from "./useKids";
import { useStories } from "./useStories";

const THEME_LABELS = {
  space: "Space",
  under_the_sea: "Under the sea",
  medieval_fantasy: "Medieval fantasy",
  dinosaurs: "Dinosaurs",
};

const ADVENTURE_LABELS = {
  secret_map: "Secret map",
  talking_animal: "Talking animal",
  time_machine: "Time machine",
  magic_key: "Magic key",
};

const STATUS_BADGES = {
  PROCESSING: { label: "Generating…", className: "status-processing" },
  COMPLETE: { label: "Ready", className: "status-complete" },
  FAILED: { label: "Failed", className: "status-failed" },
};

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

export default function LibraryPage() {
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const { kids } = useKids();

  const [filterKidId, setFilterKidId] = useState("");
  const { stories, isLoading: storiesLoading, error } = useStories(filterKidId);
  const visibleStories = stories?.filter((s) => s.status !== "FAILED") ?? null;

  useEffect(() => {
    if (!authLoading && !user) {
      navigate("/", { replace: true });
    }
  }, [authLoading, user, navigate]);

  if (authLoading || !user) return null;

  const showFilter = kids && kids.length > 1;

  return (
    <main className="app">
      <header className="family-header">
        <h1>My Library</h1>
        <p className="subtitle">Stories you have made</p>
      </header>

      {showFilter && (
        <div className="library-filter">
          <button
            className={`filter-pill ${filterKidId === "" ? "selected" : ""}`}
            onClick={() => setFilterKidId("")}
          >
            All
          </button>
          {kids.map((kid) => (
            <button
              key={kid.kid_id}
              className={`filter-pill ${filterKidId === kid.kid_id ? "selected" : ""}`}
              onClick={() => setFilterKidId(kid.kid_id)}
            >
              {kid.name}
            </button>
          ))}
        </div>
      )}

      {storiesLoading && (
        <div className="status-card">
          <p className="muted">Loading your library…</p>
        </div>
      )}

      {error && (
        <div className="status-card">
          <p>Could not load your library.</p>
          <p className="muted">{error}</p>
        </div>
      )}

      {!storiesLoading && !error && visibleStories && visibleStories.length === 0 && (
        <div className="status-card">
          <div className="big-emoji">📖</div>
          <p>No stories yet.</p>
          <p className="muted">
            {filterKidId ? "No stories for this kid yet." : "Make your first story to see it here."}
          </p>
          <Link to="/" className="primary-btn">
            Make a story
          </Link>
        </div>
      )}

      {!storiesLoading && !error && visibleStories && visibleStories.length > 0 && (
        <section className="card-section">
          <div className="library-grid">
            {visibleStories.map((story) => {
              const badge = STATUS_BADGES[story.status] ?? {
                label: story.status,
                className: "status-unknown",
              };
              const themeLabel = THEME_LABELS[story.theme] || story.theme;
              const adventureLabel = ADVENTURE_LABELS[story.adventure] || story.adventure;
              return (
                <div key={story.story_id} className="library-card">
                  <div className="library-card-body">
                    <div className="library-card-header">
                      <span className="library-card-name">
                        {story.name || "Untitled"}
                      </span>
                      <span className={`status-badge ${badge.className}`}>
                        {badge.label}
                      </span>
                    </div>
                    <div className="library-card-meta muted">
                      {themeLabel} · {adventureLabel}
                    </div>
                    <div className="library-card-date muted">
                      {formatDate(story.created_at)}
                    </div>
                  </div>
                  {story.status === "COMPLETE" && story.download_url && (
                      <a
                      className="primary-btn library-card-btn"
                      href={story.download_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      <div className="back-link-row">
        <Link to="/" className="back-link">
          ← Back to story
        </Link>
      </div>
    </main>
  );
}
