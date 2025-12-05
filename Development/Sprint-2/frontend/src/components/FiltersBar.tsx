import { useMemo, useState } from "react";

type Props = {
  options: any;
  filters: any;
  onChange: (f: any) => void;
  onApply: () => void;
  onReset: () => void;
  selectedColumns: string[];
  onColumnsChange: (c: string[]) => void;
};

function ToggleList({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (val: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(
    () => (query ? options.filter((v) => v.toLowerCase().includes(query.toLowerCase())) : options),
    [options, query]
  );

  return (
    <div className="filter-group">
      <label>{label}</label>
      <div className="select-box">
        <div className="selected-values">
          {selected.length === 0 ? <span className="placeholder">Select...</span> : selected.join(", ")}
        </div>
        <div className="options-menu">
          <div className="options-search">
            <input
              type="text"
              placeholder="Search values..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {(filtered || []).map((v) => {
            const active = selected.includes(v);
            return (
              <div
                key={v}
                className={`option-row ${active ? "active" : ""}`}
                onClick={() => onToggle(v)}
              >
                <span>{v}</span>
                {active && <span className="check">✓</span>}
              </div>
            );
          })}
          {filtered.length === 0 && <div className="option-row muted">No matches</div>}
        </div>
      </div>
    </div>
  );
}

export function FiltersBar({ options, filters, onChange, onApply, onReset, selectedColumns, onColumnsChange }: Props) {
  const toggle = (key: string, val: string) => {
    onChange((prev: any) => {
      const current: string[] = prev[key] || [];
      const exists = current.includes(val);
      const next = exists ? current.filter((v) => v !== val) : [...current, val];
      return { ...prev, [key]: next };
    });
  };

  return (
    <div className="filters card">
      <div className="filter-group" style={{ marginBottom: 10 }}>
        <label>Select filter columns</label>
        <div className="chips scroll-row">
          {(options.columns || []).map((col: any) => {
            const active = selectedColumns.includes(col.name);
            return (
              <button
                key={col.name}
                type="button"
                className={`chip ${active ? "chip-active" : ""}`}
                onClick={() => {
                  const exists = active;
                  const next = exists
                    ? selectedColumns.filter((c) => c !== col.name)
                    : [...selectedColumns, col.name];
                  onColumnsChange(next);
                  onChange((f: any) => {
                    const copy = { ...f };
                    Object.keys(copy).forEach((k) => {
                      if (!next.includes(k) && !["date_from", "date_to"].includes(k)) {
                        delete copy[k];
                      }
                    });
                    return copy;
                  });
                }}
              >
                {col.name}
              </button>
            );
          })}
        </div>
      </div>
      <div className="filter-row">
        {(options.columns || [])
          .filter((col: any) => selectedColumns.includes(col.name))
          .map((col: any) => (
            <ToggleList
              key={col.name}
              label={col.name}
              options={col.values || []}
              selected={filters[col.name] || []}
              onToggle={(v) => toggle(col.name, v)}
            />
          ))}
        <div className="filter-group">
          <label>Date From</label>
          <input
            type="date"
            value={filters.date_from || ""}
            onChange={(e) => onChange((f: any) => ({ ...f, date_from: e.target.value }))}
          />
        </div>
        <div className="filter-group">
          <label>Date To</label>
          <input
            type="date"
            value={filters.date_to || ""}
            onChange={(e) => onChange((f: any) => ({ ...f, date_to: e.target.value }))}
          />
        </div>
      </div>
      <div className="filter-actions">
        <button className="btn" onClick={onApply}>
          Apply filters
        </button>
        <button className="btn ghost" type="button" onClick={onReset}>
          Clear filters & dashboard
        </button>
      </div>
    </div>
  );
}
