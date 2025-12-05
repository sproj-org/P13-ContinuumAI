import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { FiltersBar } from "./components/FiltersBar";
import { ChatPanel } from "./components/ChatPanel";
import { KPIGrid } from "./components/KPIGrid";
import { PlotlyChart } from "./components/PlotlyChart";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type PlotlyObject = { data: any[]; layout?: any; config?: any; type?: string };
type Kpi = { type: "kpi"; title: string; body: string };
type Message = { role: "user" | "assistant"; content: string };

export default function App() {
  const [results, setResults] = useState<PlotlyObject[]>([]);
  const [kpis, setKpis] = useState<Kpi[]>([]);
  const [filters, setFilters] = useState<any>({});
  const [options, setOptions] = useState<any>({});
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [token, setToken] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [debugText, setDebugText] = useState<string>("");
  const [showDebug, setShowDebug] = useState<boolean>(false);

  // Demo auth: auto-login/register demo user once
  useEffect(() => {
    const bootstrap = async () => {
      try {
        await axios.post(`${API_BASE}/auth/register`, {
          username: "demo",
          email: "demo@example.com",
          password: "demopass",
        });
      } catch (_) {
        /* user likely exists */
      }
      const form = new URLSearchParams();
      form.append("username", "demo");
      form.append("password", "demopass");
      const res = await axios.post(`${API_BASE}/auth/login`, form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      setToken(res.data.access_token);
    };
    bootstrap().catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const fetchFilters = async () => {
      const res = await axios.get(`${API_BASE}/filters`);
      setOptions(res.data);
    };
    fetchFilters().catch(() => {});
  }, []);

  const authHeader = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : {}), [token]);

  const runQuery = async (prompt: string, overrideFilters?: any) => {
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(
        `${API_BASE}/query`,
        { message: prompt, filters: overrideFilters ?? filters },
        { headers: { "Content-Type": "application/json", ...authHeader } }
      );
      if (res.data.status === "success") {
        setResults(res.data.results || []);
        setKpis(res.data.kpis || []);
        const dbg = res.data?.meta?.debug;
        if (dbg) {
          setDebugText(JSON.stringify(dbg, null, 2));
        }
        setMessages((prev) => [...prev, { role: "assistant", content: "Updated the dashboard." }]);
      } else {
        const dbg = res.data?.meta?.debug;
        setError(res.data?.message || "No results returned");
        if (dbg) setDebugText(JSON.stringify(dbg, null, 2));
        setResults([]);
        setKpis([]);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: res.data?.message || "No results returned" },
        ]);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "Request failed");
      setResults([]);
      setKpis([]);
      setMessages((prev) => [...prev, { role: "assistant", content: e?.message || "Request failed" }]);
    } finally {
      setLoading(false);
    }
  };

  const resetAll = () => {
    setFilters({});
    setResults([]);
    setKpis([]);
    setError("");
  };

  return (
    <div className="page">
      <aside className="sidebar">
        <h1 className="logo">Continuum</h1>
        <ChatPanel onSend={runQuery} loading={loading} messages={messages} />
        {debugText && (
          <div className="debug-panel">
            <button className="btn ghost small" onClick={() => setShowDebug(!showDebug)}>
              {showDebug ? "Hide details" : "Show details"}
            </button>
            {showDebug && <pre className="debug-text">{debugText}</pre>}
          </div>
        )}
      </aside>
      <main className="content">
        <header className="header">
          <div>
            <div className="eyebrow">Vizro-powered</div>
            <h2>Sales Intelligence Dashboard</h2>
          </div>
          <div className="header-actions">
            <button className="btn ghost small" onClick={() => setShowDebug(!showDebug)} disabled={!debugText}>
              {showDebug ? "Hide generated code/debug" : "Show generated code/debug"}
            </button>
          </div>
        </header>

        <div className="workspace">
          <section className="filters-pane card">
            <div className="filters-header">
              <div>
                <div className="eyebrow">Filters</div>
                <h4>Refine the dashboard</h4>
              </div>
              <button className="btn ghost small" onClick={resetAll}>
                Clear dashboard
              </button>
            </div>
            <FiltersBar
              options={options}
              filters={filters}
              onChange={setFilters}
              onApply={() => runQuery("Update with filters")}
              onReset={resetAll}
              selectedColumns={selectedColumns}
              onColumnsChange={setSelectedColumns}
            />
          </section>

          <section className="dashboard-pane">
            {error && <div className="error">{error}</div>}

            <KPIGrid kpis={kpis} />

            {loading && <div className="loader">Loading charts...</div>}

            <div className="stack">
              {results.map((chart, idx) =>
                chart.type === "kpi" ? null : (
                  <div key={idx} className="card chart">
                    <PlotlyChart chartData={chart} chartId={`chart-${idx}`} />
                  </div>
                )
              )}
            </div>
          </section>
        </div>

        {showDebug && debugText && (
          <section className="debug-drawer card">
            <div className="debug-title">Generated code & debug</div>
            <pre className="debug-text">{debugText}</pre>
          </section>
        )}
      </main>
    </div>
  );
}
