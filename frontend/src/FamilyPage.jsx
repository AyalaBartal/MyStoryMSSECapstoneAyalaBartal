import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./useAuth";
import { apiCall } from "./api";

const NAME_MAX_LENGTH = 30;
const CURRENT_YEAR = new Date().getFullYear();
const MIN_BIRTH_YEAR = 2010;

export default function FamilyPage() {
  const { user, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  // Auth gate — same pattern as before. Redirect anonymous users home.
  useEffect(() => {
    if (!authLoading && !user) {
      navigate("/", { replace: true });
    }
  }, [authLoading, user, navigate]);

  // Kid list state.
  const [kids, setKids] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  // "Add a kid" form state.
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newBirthYear, setNewBirthYear] = useState("");
  const [newHero, setNewHero] = useState("");
  const [addError, setAddError] = useState(null);
  const [addSubmitting, setAddSubmitting] = useState(false);

  // Per-kid removal state — tracks which kid is mid-delete.
  const [removingKidId, setRemovingKidId] = useState(null);

  // Load the kids list when the user is signed in.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function loadKids() {
      setListLoading(true);
      setListError(null);
      try {
        const data = await apiCall("GET", "/kids");
        if (!cancelled) {
          setKids(data.kids || []);
        }
      } catch (err) {
        if (!cancelled) {
          setListError(err.message);
        }
      } finally {
        if (!cancelled) {
          setListLoading(false);
        }
      }
    }

    loadKids();
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function handleAddKid(e) {
  e.preventDefault();

  const trimmedName = newName.trim();
  if (trimmedName.length < 1 || trimmedName.length > NAME_MAX_LENGTH) {
    setAddError(`Name must be 1-${NAME_MAX_LENGTH} characters`);
    return;
  }
  const yearNum = parseInt(newBirthYear, 10);
  if (
    isNaN(yearNum) ||
    yearNum < MIN_BIRTH_YEAR ||
    yearNum > CURRENT_YEAR
  ) {
    setAddError(
      `Birth year must be between ${MIN_BIRTH_YEAR} and ${CURRENT_YEAR}`,
    );
    return;
  }
  if (newHero !== "boy" && newHero !== "girl") {
    setAddError("Pick a hero");
    return;
  }

  setAddSubmitting(true);
  setAddError(null);
  try {
    const newKid = await apiCall("POST", "/kids", {
      name: trimmedName,
      birth_year: yearNum,
      hero: newHero,
      // Hardcoded for now — future polish will let parents pick
      // an avatar from the existing card library.
      avatar_card_id: "default",
    });
    setKids([newKid, ...kids]);
    setNewName("");
    setNewBirthYear("");
    setNewHero("");
    setShowAddForm(false);
  } catch (err) {
    setAddError(err.message);
  } finally {
    setAddSubmitting(false);
  }
}

  async function handleRemoveKid(kid) {
    const confirmed = window.confirm(
      `Remove ${kid.name}'s profile? Stories already created for ${kid.name} will not be deleted.`,
    );
    if (!confirmed) return;

    setRemovingKidId(kid.kid_id);
    try {
      await apiCall("DELETE", `/kids/${kid.kid_id}`);
      setKids(kids.filter((k) => k.kid_id !== kid.kid_id));
    } catch (err) {
      alert(`Could not remove ${kid.name}: ${err.message}`);
    } finally {
      setRemovingKidId(null);
    }
  }

  // Render-time auth gate (matches the redirect behavior).
  if (authLoading || !user) {
    return null;
  }

  return (
    <main className="app">
      <header className="family-header">
        <h1>My Family</h1>
        <p className="subtitle">Manage your kids' profiles</p>
      </header>

      {listLoading && (
        <div className="status-card">
          <p className="muted">Loading your family…</p>
        </div>
      )}

      {listError && (
        <div className="status-card">
          <p>Couldn't load your family.</p>
          <p className="muted">{listError}</p>
        </div>
      )}

      {!listLoading && !listError && kids.length === 0 && !showAddForm && (
        <div className="status-card">
          <div className="big-emoji">👨‍👩‍👧</div>
          <p>No kids yet.</p>
          <p className="muted">Add your first kid to get started.</p>
          <button
            className="primary-btn"
            onClick={() => setShowAddForm(true)}
          >
            + Add a kid
          </button>
        </div>
      )}

      {!listLoading && !listError && kids.length > 0 && (
        <section className="card-section">
          <div className="kids-grid">
            {kids.map((kid) => {
              const age = CURRENT_YEAR - kid.birth_year;
              const isRemoving = removingKidId === kid.kid_id;
              return (
                <div key={kid.kid_id} className="kid-card">
                  <div className="kid-avatar" aria-hidden="true">
                    {kid.name[0]?.toUpperCase() || "?"}
                  </div>
                  <div className="kid-info">
                    <div className="kid-name">{kid.name}</div>
                    <div className="kid-age muted">
                      {age} {age === 1 ? "year" : "years"} old
                    </div>
                  </div>
                  <button
                    className="kid-remove-btn"
                    onClick={() => handleRemoveKid(kid)}
                    disabled={isRemoving}
                    title="Remove profile"
                  >
                    {isRemoving ? "…" : "Remove"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {!showAddForm && kids.length > 0 && (
        <button
          className="secondary-btn add-kid-btn"
          onClick={() => setShowAddForm(true)}
        >
          + Add another kid
        </button>
      )}

      {showAddForm && (
        <section className="card-section add-kid-form">
          <h2>Add a kid</h2>
          <form onSubmit={handleAddKid}>
            <div className="field">
              <label htmlFor="kid-name">Name</label>
              <input
                id="kid-name"
                type="text"
                className="text-input"
                value={newName}
                maxLength={NAME_MAX_LENGTH}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="What's their name?"
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="kid-birth-year">Birth year</label>
              <input
                id="kid-birth-year"
                type="number"
                className="text-input"
                value={newBirthYear}
                min={MIN_BIRTH_YEAR}
                max={CURRENT_YEAR}
                onChange={(e) => setNewBirthYear(e.target.value)}
                placeholder={String(CURRENT_YEAR - 7)}
              />
            </div>

            <div className="field">
              <label>Hero</label>
              <div className="hero-picker">
                <button
                  type="button"
                  className={`hero-option ${newHero === "boy" ? "selected" : ""}`}
                  onClick={() => setNewHero("boy")}
                >
                  Boy
                </button>
                <button
                  type="button"
                  className={`hero-option ${newHero === "girl" ? "selected" : ""}`}
                  onClick={() => setNewHero("girl")}
                >
                  Girl
                </button>
              </div>
              <p className="muted hero-hint">
                The hero stays editable when creating each story.
              </p>
            </div>

            {addError && <p className="form-error">{addError}</p>}

            <div className="action-row">
              <button
                type="submit"
                className="primary-btn"
                disabled={addSubmitting}
              >
                {addSubmitting ? "Adding…" : "Add kid"}
              </button>
              <button
                type="button"
                className="secondary-btn"
                onClick={() => {
                  setShowAddForm(false);
                  setNewName("");
                  setNewBirthYear("");
                  setNewHero("");
                  setAddError(null);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
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