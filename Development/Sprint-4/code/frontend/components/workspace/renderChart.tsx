"use client";

import { Column, Histogram, Line, Pie } from "@ant-design/plots";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import {
  buildCategoricalSeries,
  buildHistogramData,
  buildPieData,
  chartMetricLabel,
  CHART_PALETTE,
  type CategoricalSeriesDatum,
  metricColumnCandidates,
} from "@/lib/chart-rendering";
import { chartDimensionLabel } from "@/lib/chart-display";

type ChartRows = Array<Record<string, unknown>>;

function getAxisValues(chartSpec: ChartSpecV1, rows: ChartRows) {
  const xField = chartSpec.encoding.x.field;
  const metricCandidates = metricColumnCandidates(chartSpec);
  const { labels, values, data } = buildCategoricalSeries(rows, {
    xField,
    metricCandidates,
  });

  return {
    x: labels,
    y: values,
    xField,
    xLabel: chartDimensionLabel(xField),
    categoricalData: data,
    metricLabel: chartMetricLabel(chartSpec),
    metricCandidates,
  };
}

export function renderChart(chartSpec: ChartSpecV1, rows: ChartRows) {
  const { xLabel, metricLabel, categoricalData, metricCandidates } = getAxisValues(chartSpec, rows);
  const chartType = chartSpec.chart.type;
  const histogramData = buildHistogramData(rows, metricCandidates);
  const pieData = buildPieData(categoricalData as CategoricalSeriesDatum[]);

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
        scale={{ color: { range: CHART_PALETTE } }}
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
        smooth
        style={{ stroke: "#8b5cf6" }}
        axis={{
          x: { title: xLabel, labelFill: "#94a3b8", labelAutoHide: true },
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
        x: { title: xLabel, labelFill: "#94a3b8", labelAutoHide: true },
        y: { title: metricLabel, labelFill: "#94a3b8" },
      }}
      scale={{ color: { range: CHART_PALETTE } }}
      style={{ maxWidth: 70 }}
      height={400}
    />
  );
}
