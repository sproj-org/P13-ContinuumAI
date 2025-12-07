import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { FiltersBar } from "./components/FiltersBar";
import { ChatPanel } from "./components/ChatPanel";
import { KPIGrid } from "./components/KPIGrid";
import { ChartCard } from "./components/ChartCard";

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
  const [baselineDebug, setBaselineDebug] = useState<string>("");
  const [showDebug, setShowDebug] = useState<boolean>(false);
  const [lastPrompt, setLastPrompt] = useState<string>("");
  const [baselineResults, setBaselineResults] = useState<PlotlyObject[]>([]);
  const [baselineKpis, setBaselineKpis] = useState<Kpi[]>([]);
  const [debugHistory, setDebugHistory] = useState<string[]>([]);
  const [chartAnswers, setChartAnswers] = useState<Record<string, string[]>>({});

  const extractCodeFromDebug = (debug: any): string => {
    if (!Array.isArray(debug) || !debug.length) return "";
    const first = debug[0] || {};
    const parsed = first.parsed || {};
    const codeParts: string[] = [];
    if (parsed.chart_plan?.chart_code) codeParts.push(parsed.chart_plan.chart_code);
    if (parsed.card_plan?.card_code) codeParts.push(parsed.card_plan.card_code);
    return codeParts.join("\n\n").trim();
  };

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
    setLastPrompt(prompt);
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(
        `${API_BASE}/query`,
        { message: prompt, filters: overrideFilters ?? filters },
        { headers: { "Content-Type": "application/json", ...authHeader } }
      );
      if (res.data.status === "success") {
        const safeResults = res.data.results ? JSON.parse(JSON.stringify(res.data.results)) : [];
        const safeKpis = res.data.kpis ? JSON.parse(JSON.stringify(res.data.kpis)) : [];
        setResults(safeResults);
        setKpis(safeKpis);
        const dbg = res.data?.meta?.debug;
        const codes = res.data?.meta?.debug_codes || [];
        const codeBlock = dbg ? extractCodeFromDebug(dbg) : "";
        if (codes.length) {
          setDebugHistory((prev) => [...prev, ...codes]);
          setDebugText([...debugHistory, ...codes].filter(Boolean).join("\n\n"));
          setBaselineDebug([...debugHistory, ...codes].filter(Boolean).join("\n\n"));
        } else if (codeBlock) {
          setDebugHistory((prev) => [...prev, codeBlock]);
          setDebugText([...debugHistory, codeBlock].join("\n\n"));
          setBaselineDebug([...debugHistory, codeBlock].join("\n\n"));
        }
        setBaselineResults(safeResults);
        setBaselineKpis(safeKpis);
        const parsedReply = res.data?.meta?.debug?.[0]?.parsed?.reply || res.data?.meta?.debug?.[0]?.raw;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: parsedReply || "Updated the dashboard with the latest plan." },
        ]);
      } else {
        const dbg = res.data?.meta?.debug;
        setError(res.data?.message || "No results returned");
        if (dbg) setDebugText(extractCodeFromDebug(dbg) || debugText);
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

  const applyFilters = async (override?: any) => {
    const payload = override ?? filters;
    const isEmptyFilters = !payload || Object.keys(payload).length === 0;
    if (isEmptyFilters) {
      // Restore baseline visuals when filters are cleared
      setResults(JSON.parse(JSON.stringify(baselineResults)));
      setKpis(JSON.parse(JSON.stringify(baselineKpis)));
      setDebugText(baselineDebug || debugText);
      return;
    }
    // If no charts yet, fall back to a normal query
    if (!results.length && !kpis.length && lastPrompt) {
      return runQuery(lastPrompt, payload);
    }
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(
        `${API_BASE}/refresh`,
        { filters: payload },
        { headers: { "Content-Type": "application/json", ...authHeader } }
      );
      if (res.data.status === "success") {
        setResults(res.data.results || []);
        setKpis(res.data.kpis || []);
        const dbg = res.data?.meta?.debug;
        const codes = res.data?.meta?.debug_codes || [];
        const codeBlock = dbg ? extractCodeFromDebug(dbg) : "";
        if (codes.length) {
          setDebugHistory((prev) => [...prev, ...codes]);
          setDebugText([...debugHistory, ...codes].filter(Boolean).join("\n\n"));
        } else if (codeBlock) {
          setDebugHistory((prev) => [...prev, codeBlock]);
          setDebugText([...debugHistory, codeBlock].join("\n\n"));
        } else {
          setDebugText(baselineDebug || debugText);
        }
      } else {
        const dbg = res.data?.meta?.debug;
        setError(res.data?.message || "No results returned");
        const codes = res.data?.meta?.debug_codes || [];
        const codeBlock = dbg ? extractCodeFromDebug(dbg) : "";
        if (codes.length) {
          setDebugHistory((prev) => [...prev, ...codes]);
          setDebugText([...debugHistory, ...codes].filter(Boolean).join("\n\n"));
        } else if (codeBlock) {
          setDebugHistory((prev) => [...prev, codeBlock]);
          setDebugText([...debugHistory, codeBlock].join("\n\n"));
        }
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "Filter refresh failed");
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({});
    setError("");
    // re-render existing charts without filters
    applyFilters({});
  };

  const askAboutChart = async (chartId: string, question: string) => {
    try {
      const res = await axios.post(
        `${API_BASE}/question`,
        { chart_id: chartId, question },
        { headers: { "Content-Type": "application/json", ...authHeader } }
      );
      const answer = res.data?.answer || res.data?.message || "No answer returned.";
      setChartAnswers((prev) => ({
        ...prev,
        [chartId]: [...(prev[chartId] || []), answer],
      }));
      setMessages((prev) => [...prev, { role: "assistant", content: answer }]);
      return answer;
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || "Question failed";
      setChartAnswers((prev) => ({
        ...prev,
        [chartId]: [...(prev[chartId] || []), msg],
      }));
      return msg;
    }
  };

  return (
    <div className="page">
      <aside className="sidebar">
        <h1 className="logo">Continuum</h1>
        <ChatPanel onSend={runQuery} loading={loading} messages={messages} />
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
            </div>
            <FiltersBar
              options={options}
              filters={filters}
              onChange={setFilters}
              onApply={applyFilters}
              onReset={clearFilters}
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
                  <ChartCard
                    key={idx}
                    chart={chart}
                    chartId={`chart-${idx}`}
                    onAsk={askAboutChart}
                    answers={chartAnswers[`chart-${idx}`]}
                  />
                )
              )}
            </div>
          </section>
        </div>

        {showDebug && debugText && (
          <section className="debug-drawer card">
            <div className="debug-title">Generated code</div>
            <pre className="debug-text">{debugText}</pre>
          </section>
        )}
      </main>
    </div>
  );
}
