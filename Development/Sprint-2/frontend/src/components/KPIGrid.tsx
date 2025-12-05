type Props = {
  kpis: { title: string; body: string }[];
};

export function KPIGrid({ kpis }: Props) {
  if (!kpis || !kpis.length) return null;
  return (
    <div className="kpi-grid">
      {kpis.map((kpi, idx) => (
        <div key={idx} className="card kpi">
          <h4>{kpi.title}</h4>
          <p>{kpi.body}</p>
        </div>
      ))}
    </div>
  );
}
