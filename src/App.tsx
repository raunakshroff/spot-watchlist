import { useEffect, useState } from "react";
import { Activity, LayoutDashboard, Layers, LineChart, Newspaper, History as HistoryIcon, Archive, ExternalLink } from "lucide-react";
import type { DroppedStock, HistoryEntry, IndexConstituentsData, IndexHistoryData, IndicesData, Meta, SovrennEntry, WatchlistStock } from "./types";
import { SovrennView } from "./components/SovrennView";
import { Overview } from "./components/Overview";
import { HistoryView } from "./components/HistoryView";
import { DroppedView } from "./components/DroppedView";
import { SectorView } from "./components/SectorView";
import { IndexView } from "./components/IndexView";

type Tab = "overview" | "sector" | "index" | "sovrenn" | "history" | "dropped";

async function loadJson<T>(path: string): Promise<T> {
  const base = import.meta.env.BASE_URL;
  const res = await fetch(`${base}${path.replace(/^\//, "")}`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const TAB_HASH: Record<Tab, string> = {
  overview: "watchlist",
  sector: "sector",
  index: "indexes",
  sovrenn: "sovrenn",
  history: "history",
  dropped: "dropped",
};

function tabFromHash(): Tab {
  const h = window.location.hash.replace(/^#/, "").toLowerCase();
  if (h === "overview") return "overview";
  const hit = (Object.keys(TAB_HASH) as Tab[]).find((t) => TAB_HASH[t] === h);
  return hit ?? "overview";
}

export default function App() {
  const [tab, setTabState] = useState<Tab>(tabFromHash);
  const setTab = (t: Tab) => {
    setTabState(t);
    if (window.location.hash !== `#${TAB_HASH[t]}`) window.history.replaceState(null, "", `#${TAB_HASH[t]}`);
    window.scrollTo({ top: 0 });
  };
  useEffect(() => {
    const onHash = () => setTabState(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const [watchlist, setWatchlist] = useState<WatchlistStock[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [dropped, setDropped] = useState<DroppedStock[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [indices, setIndices] = useState<IndicesData | null>(null);
  const [indexHistory, setIndexHistory] = useState<IndexHistoryData | null>(null);
  const [indexConstituents, setIndexConstituents] = useState<IndexConstituentsData | null>(null);
  const [indicesError, setIndicesError] = useState<string | null>(null);
  const [sovrenn, setSovrenn] = useState<SovrennEntry[] | null>(null);
  const [sovrennError, setSovrennError] = useState<string | null>(null);
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

    loadJson<IndexHistoryData>("data/index_history.json")
      .then(setIndexHistory)
      .catch(() => setIndexHistory(null));

    loadJson<IndexConstituentsData>("data/index_constituents.json")
      .then(setIndexConstituents)
      .catch(() => setIndexConstituents(null));

    loadJson<SovrennEntry[]>("data/sovrenn.json")
      .then(setSovrenn)
      .catch((e: Error) => setSovrennError(e.message));
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

  const tabs: { id: Tab; label: string; icon: typeof Activity; count?: number }[] = [
    { id: "overview", label: "Watchlist", icon: LayoutDashboard, count: watchlist.length },
    { id: "sector", label: "Sector", icon: Layers },
    { id: "index", label: "Indexes", icon: LineChart, count: indices?.indices?.length ? indices.indices.length - 1 : undefined },
    { id: "sovrenn", label: "Sovrenn", icon: Newspaper, count: sovrenn?.length },
    { id: "history", label: "History", icon: HistoryIcon },
    { id: "dropped", label: "Dropped", icon: Archive, count: dropped.length },
  ];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <div className="brand-mark">
              <Activity size={18} />
            </div>
            <div className="brand-text">
              <h1>{meta.title}</h1>
              <p>NSE spot dashboard · {meta.timezone}</p>
            </div>
          </div>
          <div className="meta-chip" title="Last market update">
            <span className="live-dot" />
            <span className="meta-label">Updated</span>
            <span className="meta-date">{meta.lastMarketUpdate}</span>
          </div>
        </div>
      </header>
      <nav className="tabs" aria-label="Sections">
          <div className="tabs-inner">
            {tabs.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`tab ${tab === t.id ? "active" : ""}`}
                  onClick={() => setTab(t.id)}
                  aria-current={tab === t.id ? "page" : undefined}
                >
                  <Icon size={15} aria-hidden />
                  <span>{t.label}</span>
                  {t.count != null && <span className="tab-count">{t.count}</span>}
                </button>
              );
            })}
          </div>
        </nav>

      <main className="app">
      {tab === "overview" && (
        <Overview
          stocks={watchlist}
          search={search}
          setSearch={setSearch}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          indices={indices}
          onOpenIndex={() => setTab("index")}
        />
      )}
      {tab === "sector" && <SectorView stocks={watchlist} />}
      {tab === "index" && (
        <IndexView data={indices} history={indexHistory} constituents={indexConstituents} loadError={indicesError} watchlist={watchlist} />
      )}
      {tab === "sovrenn" && <SovrennView data={sovrenn} loadError={sovrennError} />}
      {tab === "history" && <HistoryView history={history} />}
      {tab === "dropped" && <DroppedView dropped={dropped} />}

      <footer className="footer">
        <div>
          Last update <strong>{meta.lastMarketUpdate}</strong>
          {" · "}
          <a href={meta.repoUrl} target="_blank" rel="noreferrer">
            GitHub repo <ExternalLink size={12} aria-hidden />
          </a>
        </div>
        <div>{meta.disclaimer}</div>
      </footer>
      </main>
    </div>
  );
}
