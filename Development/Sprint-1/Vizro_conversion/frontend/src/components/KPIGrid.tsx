type Props = {
  kpis: { title: string; body: string }[];
};

export function KPIGrid({ kpis }: Props) {
  if (!kpis || !kpis.length) return null;
  const formatTitle = (t: string) => {
    if (!t) return "KPI";
    const cleaned = t.replace(/_/g, " ");
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  };
  return (
    <div className="kpi-grid">
      {kpis.map((kpi, idx) => (
        <div key={idx} className="card kpi">
          <h4>{formatTitle(kpi.title)}</h4>
          <div className="kpi-body">{kpi.body}</div>
        </div>
      ))}
    </div>
  );
}
