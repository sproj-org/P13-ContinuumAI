"use client";

import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import type { ChartSpecV1 } from "@/lib/types/chartspec";

type ChartRows = Array<Record<string, unknown>>;

function toDisplayLabel(value: unknown): string {
  if (value == null) return "NULL";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return `${value}`;
  return JSON.stringify(value);
}

function getAxisValues(chartSpec: ChartSpecV1, rows: ChartRows) {
  const xField = chartSpec.encoding.x.field;
  const metric = chartSpec.encoding.y[0];
  const yField = metric.alias ?? "agg_value";

  return {
    x: rows.map((row) => toDisplayLabel(row[xField])),
    y: rows.map((row) => Number(row[yField] ?? 0)),
    xField,
    yField,
    metricLabel: `${metric.aggregation.toUpperCase()}(${metric.field})`,
  };
}

export function renderChart(chartSpec: ChartSpecV1, rows: ChartRows) {
  const { x, y, xField, metricLabel } = getAxisValues(chartSpec, rows);
  const chartType = chartSpec.chart.type;
  const categoricalData = x.map((category, index) => ({
    category,
    value: y[index] ?? 0,
  }));
  const histogramData = y.map((value) => ({ value }));
  const pieData = x.map((type, index) => ({
    type,
    value: y[index] ?? 0,
  }));

  if (chartType === "pie") {
    return (
      <Pie
        data={pieData}
        angleField="value"
        colorField="type"
        innerRadius={0.3}
        label={{ text: "value", position: "inside" }}
        legend={{ color: { position: "bottom" } }}
        tooltip={{ title: "type" }}
        scale={{ color: { range: ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444"] } }}
        height={400}
      />
    );
  }

  if (chartType === "line") {
    return (
      <Line
        data={categoricalData}
        xField="category"
        yField="value"
        point
        shapeField="smooth"
        style={{ stroke: "#8b5cf6" }}
        axis={{
          x: { title: xField, labelFill: "#94a3b8" },
          y: { title: metricLabel, labelFill: "#94a3b8" },
        }}
        height={400}
      />
    );
  }

  if (chartType === "histogram") {
    return (
      <Histogram
        data={histogramData}
        binField="value"
        style={{ fill: "#4f46e5", fillOpacity: 0.8 }}
        axis={{
          x: { title: metricLabel, labelFill: "#94a3b8" },
          y: { title: "Frequency", labelFill: "#94a3b8" },
        }}
        height={400}
      />
    );
  }

  return (
    <Column
      data={categoricalData}
      xField="category"
      yField="value"
      colorField="category"
      axis={{
        x: { title: xField, labelFill: "#94a3b8" },
        y: { title: metricLabel, labelFill: "#94a3b8" },
      }}
      scale={{ color: { range: ["#8b5cf6", "#3b82f6", "#4f46e5", "#6366f1", "#f59e0b", "#ef4444"] } }}
      style={{ maxWidth: 70 }}
      height={400}
    />
  );
}
