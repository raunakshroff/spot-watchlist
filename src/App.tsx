import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import type { DroppedStock, HistoryEntry, IndicesData, Meta, WatchlistStock } from "./types";
import { Overview } from "./components/Overview";
import { HistoryView } from "./components/HistoryView";
import { DroppedView } from "./components/DroppedView";
import { SectorView } from "./components/SectorView";
import { IndexView } from "./components/IndexView";

type Tab = "overview" | "sector" | "index" | "history" | "dropped";

async function loadJson<T>(path: string): Promise<T> {
  const base = import.meta.env.BASE_URL;
  const res = await fetch(`${base}${path.replace(/^\//, "")}`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [watchlist, setWatchlist] = useState<WatchlistStock[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [dropped, setDropped] = useState<DroppedStock[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [indices, setIndices] = useState<IndicesData | null>(null);
  const [indicesError, setIndicesError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");

  useEffect(() => {
    Promise.all([
      loadJson<WatchlistStock[]>("data/watchlist.json"),
      loadJson<HistoryEntry[]>("data/history.json"),
      loadJson<DroppedStock[]>("data/dropped.json"),
      loadJson<Meta>("data/meta.json"),
    ])
      .then(([w, h, d, m]) => {
        setWatchlist(w);
        setHistory(h);
        setDropped(d);
        setMeta(m);
      })
      .catch((e: Error) => setError(e.message));

    loadJson<IndicesData>("data/indices.json")
      .then(setIndices)
      .catch((e: Error) => setIndicesError(e.message));
  }, []);

  if (error) {
    return (
      <div className="loading">
        <div>
          Failed to load data: {error}
          <br />
          <span style={{ fontSize: "0.85rem" }}>Check public/data/*.json</span>
        </div>
      </div>
    );
  }

  if (!meta) {
    return <div className="loading">Loading Spot Watchlist…</div>;
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand-mark">
            <Activity size={22} />
          </div>
          <div>
            <h1>{meta.title}</h1>
            <p>NSE technical dashboard · {meta.timezone}</p>
          </div>
        </div>
        <div className="meta-chip">
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--green)" }} />
          last market update · {meta.lastMarketUpdate}
        </div>
      </header>

      <nav className="tabs" aria-label="Sections">
        <button
          type="button"
          className={`tab ${tab === "overview" ? "active" : ""}`}
          onClick={() => setTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`tab ${tab === "sector" ? "active" : ""}`}
          onClick={() => setTab("sector")}
        >
          Sector
        </button>
        <button
          type="button"
          className={`tab ${tab === "index" ? "active" : ""}`}
          onClick={() => setTab("index")}
        >
          vs Nifty
        </button>
        <button
          type="button"
          className={`tab ${tab === "history" ? "active" : ""}`}
          onClick={() => setTab("history")}
        >
          History
        </button>
        <button
          type="button"
          className={`tab ${tab === "dropped" ? "active" : ""}`}
          onClick={() => setTab("dropped")}
        >
          Dropped ({dropped.length})
        </button>
      </nav>

      {tab === "overview" && (
        <Overview
          stocks={watchlist}
          search={search}
          setSearch={setSearch}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
        />
      )}
      {tab === "sector" && <SectorView stocks={watchlist} />}
      {tab === "index" && <IndexView data={indices} loadError={indicesError} />}
      {tab === "history" && <HistoryView history={history} />}
      {tab === "dropped" && <DroppedView dropped={dropped} />}

      <footer className="footer">
        <div>
          Last update: <strong style={{ color: "var(--text-muted)" }}>{meta.lastMarketUpdate}</strong>
          {" · "}
          <a href={meta.repoUrl} target="_blank" rel="noreferrer">
            GitHub repo
          </a>
        </div>
        <div>{meta.disclaimer}</div>
      </footer>
    </div>
  );
}
