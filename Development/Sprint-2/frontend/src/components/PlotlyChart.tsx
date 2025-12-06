'use client';

import Plot from "react-plotly.js";

type PlotlyObject = { data: any[]; layout?: any; config?: any };

interface Props {
  chartData: PlotlyObject;
  chartId: string;
}

export function PlotlyChart({ chartData, chartId }: Props) {
  const baseLayout = chartData.layout || {};
  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#0b1220",
    font: { color: "#e2e8f0", family: "Inter, 'Helvetica Neue', Arial, sans-serif" },
    autosize: true,
    margin: { l: 70, r: 40, t: 60, b: 60, ...(baseLayout as any).margin },
    hoverlabel: {
      bgcolor: "#0f172a",
      bordercolor: "#1f2937",
      font: { color: "#f1f5f9", family: "Inter, 'Helvetica Neue', Arial, sans-serif" },
      ...(baseLayout as any).hoverlabel,
    },
    ...baseLayout,
  };

  const config = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    toImageButtonOptions: { format: "png", height: 600, width: 1000, scale: 2 },
    ...(chartData.config || {}),
  };

  return (
    <div id={chartId} className="chart-shell">
      <Plot data={chartData.data} layout={layout} config={config} useResizeHandler style={{ width: "100%", height: layout.height || 520 }} />
    </div>
  );
}
