import { useEffect, useState } from "react";
import Button from "./ui/Button";
import Card from "./ui/Card";
import { AIQueryLog, AIStatus, getAIStatus, listAIQueries } from "../services/ai";
import { ApiError } from "../services/api";

interface AIPanelProps {
  targetType: "alert" | "incident";
  targetId: string;
  canRequest: boolean;
  onRequest: () => Promise<AIQueryLog>;
  requestLabel: string;
}

const SECTION_STYLE: Record<string, string> = {
  observed_facts: "text-vexus-text",
  inferences: "text-blue-300",
  hypotheses: "text-yellow-300",
  recommendations: "text-green-300",
};

const SECTION_LABEL: Record<string, string> = {
  observed_facts: "Observed Facts",
  inferences: "Inferences",
  hypotheses: "Hypotheses",
  recommendations: "Recommendations",
};

function ResponseSections({ log }: { log: AIQueryLog }) {
  const sections: (keyof AIQueryLog)[] = ["observed_facts", "inferences", "hypotheses", "recommendations"];
  return (
    <div className="space-y-3">
      {sections.map((key) => {
        const items = log[key] as string[];
        if (!items || items.length === 0) return null;
        return (
          <div key={key}>
            <div className="text-xs font-medium text-vexus-muted mb-1">{SECTION_LABEL[key]}</div>
            <ul className={`text-sm space-y-1 ${SECTION_STYLE[key]}`}>
              {items.map((item, i) => (
                <li key={i}>• {item}</li>
              ))}
            </ul>
          </div>
        );
      })}
      <div className="text-xs text-vexus-muted pt-1 border-t border-vexus-border">
        Confidence: {(log.confidence * 100).toFixed(0)}% · {new Date(log.created_at).toLocaleString()}
      </div>
    </div>
  );
}

export default function AIPanel({ targetType, targetId, canRequest, onRequest, requestLabel }: AIPanelProps) {
  const [history, setHistory] = useState<AIQueryLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);

  async function load() {
    try {
      setHistory(await listAIQueries(targetType, targetId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load AI history.");
    }
  }

  useEffect(() => {
    load();
    getAIStatus().then(setAIStatus).catch(() => setAIStatus(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId]);

  async function handleRequest() {
    setRequesting(true);
    setError(null);
    try {
      await onRequest();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI request failed.");
    } finally {
      setRequesting(false);
    }
  }

  const latest = history && history.length > 0 ? history[0] : null;

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img src="/vexusAI.png" alt="" className="h-8 w-8 rounded object-cover" />
          <h2 className="text-sm font-medium text-vexus-muted">AI Assistant</h2>
        </div>
        {canRequest && aiStatus?.configured && (
          <Button onClick={handleRequest} disabled={requesting} variant="secondary">
            {requesting ? "Thinking…" : requestLabel}
          </Button>
        )}
      </div>

      {error && <div className="text-xs text-red-400">{error}</div>}

      {canRequest && aiStatus && !aiStatus.configured && (
        <div className="rounded border border-yellow-900 bg-yellow-950/30 px-3 py-2 text-xs text-yellow-300">
          AI is visible but not active. Configure <code>AI_PROVIDER</code> and the matching provider API key on the backend.
        </div>
      )}

      {!latest && !error && (
        <p className="text-xs text-vexus-muted">
          No AI analysis yet. {canRequest ? `Click "${requestLabel}" to request one.` : ""}
        </p>
      )}

      {latest && <ResponseSections log={latest} />}
    </Card>
  );
}
