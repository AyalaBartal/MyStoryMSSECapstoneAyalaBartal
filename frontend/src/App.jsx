import { useEffect, useState } from "react";
import { CARDS } from "./cardsConfig";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 120_000;
const NAME_MAX_LENGTH = 30;
const AGE_OPTIONS = ["4", "5", "6", "7", "8", "9", "10", "11", "12"];

function CardVisual({ opt }) {
  const [imgFailed, setImgFailed] = useState(false);
  if (opt.image && !imgFailed) {
    return (
      <img
        src={opt.image}
        alt={opt.label}
        className="card-image"
        onError={() => setImgFailed(true)}
      />
    );
  }
  if (opt.emoji) return <span className="emoji">{opt.emoji}</span>;
  return <span className="big-number">{opt.label}</span>;
}

export default function App() {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [selections, setSelections] = useState({});
  const [status, setStatus] = useState("picking");
  const [storyId, setStoryId] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const trimmedName = name.trim();
  const allCardsPicked = CARDS.every((c) => selections[c.category]);
  const nameValid =
    trimmedName.length >= 1 && trimmedName.length <= NAME_MAX_LENGTH;
  const ageValid = AGE_OPTIONS.includes(age);
  const canGenerate = allCardsPicked && nameValid && ageValid;

  async function startGeneration() {
    setStatus("generating");
    setErrorMessage(null);
    try {
      const body = { name: trimmedName, age, ...selections };
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`POST /generate → ${res.status}`);
      const data = await res.json();
      setStoryId(data.story_id);
    } catch (err) {
      setStatus("failed");
      setErrorMessage(err.message);
    }
  }

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
    setName("");
    setAge("");
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
          <p>Writing {trimmedName}'s story…</p>
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
          <p>{trimmedName}'s story is ready!</p>
          <a className="primary-btn" href={downloadUrl} target="_blank" rel="noreferrer">
            📄 Open the book
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
        <p className="subtitle">Make a personalized book just for you</p>
      </header>

      <section className="card-section name-age-section">
        <div className="field">
          <label htmlFor="name">What's your name?</label>
          <input
            id="name"
            type="text"
            className="text-input"
            value={name}
            maxLength={NAME_MAX_LENGTH}
            onChange={(e) => setName(e.target.value)}
            placeholder="Type your name"
          />
        </div>
        <div className="field">
          <label htmlFor="age">How old are you?</label>
          <select
            id="age"
            className="text-input"
            value={age}
            onChange={(e) => setAge(e.target.value)}
          >
            <option value="" disabled>Pick an age</option>
            {AGE_OPTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      </section>

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
                  <CardVisual opt={opt} />
                  {opt.label && opt.emoji && <span className="label">{opt.label}</span>}
                </button>
              );
            })}
          </div>
        </section>
      ))}

      <button
        className="primary-btn sticky"
        disabled={!canGenerate}
        onClick={startGeneration}
      >
        ✨ Create my story ✨
      </button>
    </main>
  );
}