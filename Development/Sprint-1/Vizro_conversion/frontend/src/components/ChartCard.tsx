import { useState } from "react";
import { PlotlyChart } from "./PlotlyChart";

type PlotlyObject = { data: any[]; layout?: any; config?: any; type?: string };

type Props = {
  chart: PlotlyObject;
  chartId: string;
  onAsk: (chartId: string, question: string) => Promise<string | void>;
  answers?: string[];
};

export function ChartCard({ chart, chartId, onAsk, answers = [] }: Props) {
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleAsk = async () => {
    if (!question.trim()) return;
    setSubmitting(true);
    try {
      await onAsk(chartId, question.trim());
      setQuestion("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card chart">
      <PlotlyChart chartData={chart} chartId={chartId} />
      <div className="chart-qa">
        <input
          type="text"
          placeholder="Ask about this chart..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn ghost small" onClick={handleAsk} disabled={submitting}>
          {submitting ? "Asking..." : "Ask"}
        </button>
      </div>
      {answers.length > 0 && (
        <div className="chart-answers">
          {answers.map((ans, idx) => (
            <div key={idx} className="chart-answer">
              {ans}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
