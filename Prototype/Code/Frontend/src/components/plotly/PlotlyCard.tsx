'use client';

import { useEffect, useRef } from 'react';

type Props = {
  figure: any;          // { data: [...], layout?: {...} }
  height?: number;      // optional override
};

let PlotlyLib: any | null = null; // cached between renders/modules

export default function PlotlyCard({ figure, height }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    let ro: ResizeObserver | null = null;

    (async () => {
      // Only run on client
      if (!containerRef.current || !figure) return;

      // Lazy import to avoid SSR "self is not defined"
      if (!PlotlyLib) {
        const mod = await import('plotly.js-dist-min');
        PlotlyLib = mod.default ?? mod;
      }
      if (cancelled) return;

      const layout = {
        ...(figure.layout || {}),
        autosize: true,
        height: height ?? figure?.layout?.height ?? 480,
        margin: { l: 100, r: 30, t: 60, b: 60, ...(figure.layout?.margin || {}) },
      };
      const config = { responsive: true, displaylogo: false };

      await PlotlyLib.newPlot(containerRef.current, figure.data || [], layout, config);

      // Keep it responsive
      ro = new ResizeObserver(() => {
        if (!containerRef.current) return;
        PlotlyLib.Plots.resize(containerRef.current);
      });
      ro.observe(containerRef.current);
    })();

    return () => {
      cancelled = true;
      if (ro) ro.disconnect();
      if (containerRef.current && PlotlyLib) {
        try { PlotlyLib.purge(containerRef.current); } catch {}
      }
    };
  }, [figure, height]);

  return (
    <div
      ref={containerRef}
      className="w-full max-w-full"
      style={{ width: '100%', minWidth: 320 }}
    />
  );
}
