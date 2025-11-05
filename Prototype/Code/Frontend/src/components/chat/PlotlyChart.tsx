'use client';

import { useEffect, useRef, useState } from 'react';
import type { PlotlyChart as PlotlyChartType } from '@/lib/mockApiResponses';

interface PlotlyChartProps {
  chartData: PlotlyChartType;
  chartId: string;
}

export function PlotlyChart({ chartData, chartId }: PlotlyChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [Plotly, setPlotly] = useState<any>(null);

  useEffect(() => {
    // Dynamically import Plotly to avoid SSR issues
    import('plotly.js-dist-min').then((module) => {
      setPlotly(module.default);
    });
  }, []);

  useEffect(() => {
    if (chartRef.current && chartData && Plotly) {
      // Create the Plotly chart
      Plotly.newPlot(
        chartRef.current,
        chartData.data,
        {
          ...chartData.layout,
          // Override some layout properties for consistent dark theme
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(20,20,20,0.5)',
          font: { 
            color: '#ffffff',
            family: 'SF Pro Display, -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
          },
          margin: { t: 50, r: 30, b: 50, l: 60 },
          // Make it responsive
          autosize: true
        },
        {
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
          modeBarButtonsToAdd: []
        }
      );

      // Handle window resize
      const handleResize = () => {
        if (chartRef.current) {
          Plotly.Plots.resize(chartRef.current);
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current && Plotly) {
          Plotly.purge(chartRef.current);
        }
      };
    }
  }, [chartData, Plotly]);

  return (
    <div 
      ref={chartRef} 
      id={chartId}
      className="w-full h-[400px] rounded-2xl overflow-hidden"
      style={{ minHeight: '400px' }}
    />
  );
}
