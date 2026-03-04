"use client";

import dynamic from "next/dynamic";
import type { ChartSpecV1 } from "@/lib/types/chartspec";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type ChartRows = Array<Record<string, unknown>>;

function getAxisValues(chartSpec: ChartSpecV1, rows: ChartRows) {
  const xField = chartSpec.encoding.x.field;
  const metric = chartSpec.encoding.y[0];
  const yField = metric.alias ?? "agg_value";

  return {
    x: rows.map((row) => String(row[xField] ?? "NULL")),
    y: rows.map((row) => Number(row[yField] ?? 0)),
    xField,
    yField,
    metricLabel: `${metric.aggregation.toUpperCase()}(${metric.field})`,
  };
}

export function renderChart(chartSpec: ChartSpecV1, rows: ChartRows) {
  const { x, y, xField, metricLabel } = getAxisValues(chartSpec, rows);
  const chartType = chartSpec.chart.type;

  return (
    <Plot
      data={[
        chartType === "pie"
          ? {
              type: "pie" as const,
              values: y,
              labels: x,
              textinfo: "percent" as const,
              textposition: "inside" as const,
              marker: {
                colors: ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444"],
              },
              hole: 0.3,
            }
          : chartType === "line"
          ? {
              type: "scatter",
              mode: "lines+markers",
              x,
              y,
              line: { color: "#8b5cf6", width: 3 },
              marker: { color: "#8b5cf6", size: 8 },
              fill: "tozeroy",
              fillcolor: "rgba(139, 92, 246, 0.1)",
            }
          : chartType === "histogram"
          ? ({
              type: "histogram",
              x: y,
              marker: { color: "#4f46e5", opacity: 0.8 },
              nbinsx: 10,
            } as unknown as Plotly.Data)
          : {
              type: "bar",
              x,
              y,
              marker: {
                color: y.map((_, index) => ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444"][index % 6]),
                opacity: 0.9,
              },
            },
      ]}
      layout={{
        title: {
          text: `${metricLabel} by ${xField}`,
          font: { color: "#fff", size: 16 },
        },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: "#94a3b8" },
        xaxis: {
          gridcolor: "#334155",
          title: { text: xField },
        },
        yaxis: {
          gridcolor: "#334155",
          title: { text: metricLabel },
        },
        margin: { t: 60, b: 60, l: 80, r: 40 },
        showlegend: chartType === "pie",
        legend: { orientation: "h", y: -0.2 },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height: "100%", minHeight: "400px" }}
    />
  );
}
