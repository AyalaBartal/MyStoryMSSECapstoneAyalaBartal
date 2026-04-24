import { useEffect, useState } from "react";
import { CARDS } from "./cardsConfig";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 120_000; // 2 minutes

/**
 * Four high-level screens driven by `status`:
 *   "picking"    — card selection grid
 *   "generating" — spinner + polling loop
 *   "complete"   — download link + make-another button
 *   "failed"     — error message + try-again button
 */
export default function App() {
  const [selections, setSelections] = useState({});
  const [status, setStatus] = useState("picking");
  const [storyId, setStoryId] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const allPicked = CARDS.every((c) => selections[c.category]);

  async function startGeneration() {
    setStatus("generating");
    setErrorMessage(null);
    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(selections),
      });
      if (!res.ok) throw new Error(`POST /generate → ${res.status}`);
      const data = await res.json();
      setStoryId(data.story_id);
    } catch (err) {
      setStatus("failed");
      setErrorMessage(err.message);
    }
  }

  // Polling loop — runs while status === "generating" + we have a story_id.
  useEffect(() => {
    if (status !== "generating" || !storyId) return;

    const startedAt = Date.now();
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/story/${storyId}`);
        const data = await res.json();
        if (cancelled) return;

        if (data.status === "COMPLETE") {
          setDownloadUrl(data.download_url);
          setStatus("complete");
          return;
        }
        if (data.status === "FAILED") {
          setStatus("failed");
          setErrorMessage(data.error || "Pipeline failed");
          return;
        }
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          setStatus("failed");
          setErrorMessage("Took too long. Please try again.");
          return;
        }
        setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) {
          setStatus("failed");
          setErrorMessage(err.message);
        }
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [status, storyId]);

  function reset() {
    setSelections({});
    setStatus("picking");
    setStoryId(null);
    setDownloadUrl(null);
    setErrorMessage(null);
  }

  if (status === "generating") {
    return (
      <main className="app">
        <h1>📖 My Story</h1>
        <div className="status-card">
          <div className="spinner" />
          <p>Writing your story…</p>
          <p className="muted">This takes about a minute.</p>
        </div>
      </main>
    );
  }

  if (status === "complete") {
    return (
      <main className="app">
        <h1>📖 My Story</h1>
        <div className="status-card">
          <p className="big-emoji">🎉</p>
          <p>Your story is ready!</p>
          <a className="primary-btn" href={downloadUrl} target="_blank" rel="noreferrer">
            📄 Open my book
          </a>
          <button className="secondary-btn" onClick={reset}>
            Make another
          </button>
        </div>
      </main>
    );
  }

  if (status === "failed") {
    return (
      <main className="app">
        <h1>📖 My Story</h1>
        <div className="status-card">
          <p className="big-emoji">😔</p>
          <p>Something went wrong.</p>
          <p className="muted">{errorMessage}</p>
          <button className="primary-btn" onClick={reset}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="app">
      <header>
        <h1>📖 My Story</h1>
        <p className="subtitle">Pick four cards — get a personalized book</p>
      </header>

      {CARDS.map((card) => (
        <section key={card.category} className="card-section">
          <h2>{card.title}</h2>
          <div className="card-grid">
            {card.options.map((opt) => {
              const selected = selections[card.category] === opt.value;
              return (
                <button
                  key={opt.value}
                  className={`card ${selected ? "selected" : ""}`}
                  onClick={() =>
                    setSelections({ ...selections, [card.category]: opt.value })
                  }
                >
                  <span className="emoji">{opt.emoji}</span>
                  <span className="label">{opt.label}</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}

      <button
        className="primary-btn sticky"
        disabled={!allPicked}
        onClick={startGeneration}
      >
        ✨ Create my story ✨
      </button>
    </main>
  );
}