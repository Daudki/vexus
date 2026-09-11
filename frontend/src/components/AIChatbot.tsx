import { ChangeEvent, useEffect, useState } from "react";
import { Asset, listAssets } from "../services/assets";
import { Alert, listAlerts } from "../services/detection";
import { Incident, listIncidents } from "../services/incidents";
import { AIQueryLog, AIStatus, askAI, getAIStatus } from "../services/ai";
import { ApiError } from "../services/api";
import Button from "./ui/Button";

interface AIChatbotProps {
    open: boolean;
    onClose: () => void;
}

const SECTIONS: Array<[keyof AIQueryLog, string, string]> = [
    ["observed_facts", "Observed facts", "text-vexus-text"],
    ["inferences", "Inferences", "text-blue-300"],
    ["hypotheses", "Hypotheses", "text-yellow-300"],
    ["recommendations", "Recommendations", "text-green-300"],
];

export default function AIChatbot({ open, onClose }: AIChatbotProps) {
    const [status, setStatus] = useState<AIStatus | null>(null);
    const [assets, setAssets] = useState<Asset[]>([]);
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [contextType, setContextType] = useState("asset");
    const [contextId, setContextId] = useState("");
    const [question, setQuestion] = useState("What should an analyst verify next?");
    const [answer, setAnswer] = useState<AIQueryLog | null>(null);
    const [loading, setLoading] = useState(false);
    const [asking, setAsking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) return;
        setLoading(true);
        setError(null);
        Promise.all([getAIStatus(), listAssets({ limit: 200 }), listAlerts(), listIncidents()])
            .then(([ai, assetData, alertData, incidentData]) => {
                setStatus(ai);
                setAssets(assetData);
                setAlerts(alertData);
                setIncidents(incidentData);
                setContextId((current) => current || assetData[0]?.id || alertData[0]?.id || incidentData[0]?.id || "");
            })
            .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load AI context."))
            .finally(() => setLoading(false));
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const items = contextType === "asset" ? assets : contextType === "alert" ? alerts : incidents;
        setContextId(items[0]?.id || "");
        setAnswer(null);
    }, [contextType, open]);

    async function handleAsk(event: React.FormEvent) {
        event.preventDefault();
        if (!contextId || !question.trim()) return;
        setAsking(true);
        setError(null);
        try {
            setAnswer(await askAI(contextType, contextId, question.trim()));
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "AI request failed. Your session was not changed.");
        } finally {
            setAsking(false);
        }
    }

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[60] flex items-end justify-end bg-black/40 p-3 sm:p-5" onMouseDown={onClose}>
            <section className="flex max-h-[min(760px,calc(100vh-2rem))] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-vexus-accent/40 bg-vexus-panel shadow-2xl shadow-black/60" onMouseDown={(event) => event.stopPropagation()} aria-label="VEXUS AI chatbot">
                <header className="flex items-center justify-between border-b border-vexus-border bg-vexus-bg/80 px-4 py-3">
                    <div className="flex items-center gap-3">
                        <img src="/vexusAI.png" alt="VEXUS AI" className="h-10 w-10 rounded-lg object-cover" />
                        <div><h2 className="text-sm font-semibold text-white">VEXUS AI</h2><p className="text-xs text-vexus-muted">Grounded investigation assistant</p></div>
                    </div>
                    <button type="button" onClick={onClose} className="rounded px-2 py-1 text-lg text-vexus-muted hover:bg-vexus-border/40 hover:text-white" aria-label="Close AI chatbot">×</button>
                </header>

                <div className="space-y-4 overflow-y-auto p-4">
                    {error && <div className="rounded border border-red-900 bg-red-950/40 px-3 py-2 text-xs text-red-300">{error}</div>}
                    {status && !status.configured && <div className="rounded border border-yellow-900 bg-yellow-950/40 px-3 py-2 text-xs text-yellow-300">AI is not configured on this deployment. Add a provider key to activate responses.</div>}

                    <form onSubmit={handleAsk} className="space-y-3">
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                            <label className="space-y-1"><span className="text-xs text-vexus-muted">Ask about</span><select value={contextType} onChange={(event) => setContextType(event.target.value)} className="w-full rounded border border-vexus-border bg-vexus-bg px-2.5 py-2 text-sm text-vexus-text"><option value="asset">Asset</option><option value="alert">Alert</option><option value="incident">Incident</option></select></label>
                            <label className="space-y-1"><span className="text-xs text-vexus-muted">Evidence target</span><select value={contextId} onChange={(event) => setContextId(event.target.value)} disabled={loading} className="w-full rounded border border-vexus-border bg-vexus-bg px-2.5 py-2 text-sm text-vexus-text">{contextType === "asset" && assets.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}{contextType === "alert" && alerts.map((item) => <option key={item.id} value={item.id}>{item.rule_key} · {item.severity}</option>)}{contextType === "incident" && incidents.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
                        </div>
                        <div className="flex gap-2"><textarea value={question} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setQuestion(event.target.value)} rows={2} className="min-w-0 flex-1 resize-y rounded border border-vexus-border bg-vexus-bg px-3 py-2 text-sm text-vexus-text placeholder:text-vexus-muted/60 focus:outline-none focus:ring-1 focus:ring-vexus-accent" placeholder="Ask a question about the selected evidence..." /><Button type="submit" disabled={asking || loading || !contextId || !status?.configured}>{asking ? "Thinking..." : "Ask"}</Button></div>
                    </form>

                    {!answer && <div className="border border-dashed border-vexus-border px-4 py-8 text-center text-xs text-vexus-muted">Select observed evidence and ask VEXUS AI a question.</div>}
                    {answer && <div className="space-y-3 rounded-lg border border-vexus-border bg-vexus-bg/60 p-4">{SECTIONS.map(([key, label, color]) => { const items = answer[key] as string[]; return items.length ? <section key={key}><h3 className="mb-1 text-xs font-medium text-vexus-muted">{label}</h3><ul className={`space-y-1 text-sm ${color}`}>{items.map((item, index) => <li key={index}>• {item}</li>)}</ul></section> : null; })}<div className="border-t border-vexus-border pt-2 text-xs text-vexus-muted">{answer.provider} · {(answer.confidence * 100).toFixed(0)}% confidence</div></div>}
                </div>
            </section>
        </div>
    );
}
