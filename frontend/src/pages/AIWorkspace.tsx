import { ChangeEvent, useEffect, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import { Select } from "../components/ui/Form";
import { ApiError } from "../services/api";
import { AIQueryLog, AIStatus, askAI, getAIStatus, listAIQueries } from "../services/ai";
import { Asset, listAssets } from "../services/assets";
import { Alert, listAlerts } from "../services/detection";
import { Incident, listIncidents } from "../services/incidents";

const SECTIONS: Array<[keyof AIQueryLog, string, string]> = [
    ["observed_facts", "Observed facts", "text-vexus-text"],
    ["inferences", "Inferences", "text-blue-300"],
    ["hypotheses", "Hypotheses", "text-yellow-300"],
    ["recommendations", "Recommendations", "text-green-300"],
];

function contextLabel(type: string, id: string, assets: Asset[], alerts: Alert[], incidents: Incident[]): string {
    if (type === "asset") return assets.find((item) => item.id === id)?.display_name || id;
    if (type === "alert") return alerts.find((item) => item.id === id)?.description || id;
    return incidents.find((item) => item.id === id)?.title || id;
}

export default function AIWorkspace() {
    const [status, setStatus] = useState<AIStatus | null>(null);
    const [assets, setAssets] = useState<Asset[]>([]);
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [contextType, setContextType] = useState("asset");
    const [contextId, setContextId] = useState("");
    const [question, setQuestion] = useState("What should an analyst verify next?");
    const [history, setHistory] = useState<AIQueryLog[]>([]);
    const [answer, setAnswer] = useState<AIQueryLog | null>(null);
    const [loading, setLoading] = useState(true);
    const [asking, setAsking] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setLoading(true);
        try {
            const [ai, assetData, alertData, incidentData] = await Promise.all([
                getAIStatus(),
                listAssets({ limit: 200, sort_by: "last_seen", sort_desc: true }),
                listAlerts(),
                listIncidents(),
            ]);
            setStatus(ai);
            setAssets(assetData);
            setAlerts(alertData);
            setIncidents(incidentData);
            const firstId = contextType === "asset" ? assetData[0]?.id : contextType === "alert" ? alertData[0]?.id : incidentData[0]?.id;
            if (!contextId && firstId) setContextId(firstId);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load AI workspace.");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const firstId = contextType === "asset" ? assets[0]?.id : contextType === "alert" ? alerts[0]?.id : incidents[0]?.id;
        setContextId(firstId || "");
        setAnswer(null);
    }, [contextType, assets, alerts, incidents]);

    useEffect(() => {
        if (!contextId) return;
        listAIQueries(contextType, contextId).then(setHistory).catch(() => setHistory([]));
    }, [contextType, contextId]);

    async function handleAsk(event: React.FormEvent) {
        event.preventDefault();
        if (!contextId || !question.trim()) return;
        setAsking(true);
        setError(null);
        try {
            const result = await askAI(contextType, contextId, question.trim());
            setAnswer(result);
            setHistory((previous) => [result, ...previous]);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "AI request failed.");
        } finally {
            setAsking(false);
        }
    }

    const selectedLabel = contextLabel(contextType, contextId, assets, alerts, incidents);

    return (
        <Layout>
            <div className="space-y-6">
                <div className="flex items-center gap-4">
                    <img src="/vexusAI.png" alt="VEXUS AI" className="h-20 w-20 rounded-lg object-cover shadow-lg shadow-blue-950/40" />
                    <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-vexus-accent">Investigation workspace</p>
                        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">Ask VEXUS AI</h1>
                        <p className="mt-1 max-w-2xl text-sm text-vexus-muted">Ask questions against observed VEXUS evidence. The assistant does not receive raw database or network access.</p>
                    </div>
                </div>

                {status && !status.configured && (
                    <div className="rounded-lg border border-yellow-900 bg-yellow-950/40 px-4 py-3 text-sm text-yellow-300">
                        AI is not active. Configure <code className="text-yellow-200">AI_PROVIDER</code> and the matching provider key on the backend.
                    </div>
                )}
                {error && <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>}

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-[0.8fr_1.2fr]">
                    <Card className="p-5">
                        <div className="mb-4 flex items-center justify-between"><div className="flex items-center gap-2"><img src="/vexusAI.png" alt="" className="h-6 w-6 rounded object-cover" /><h2 className="text-sm font-medium text-white">Grounding context</h2></div><span className="text-xs text-vexus-muted">{status?.configured ? status.provider : "disabled"}</span></div>
                        <form onSubmit={handleAsk} className="space-y-4">
                            <label className="block space-y-1"><span className="text-xs text-vexus-muted">Context type</span><Select value={contextType} onChange={(event) => setContextType(event.target.value)}><option value="asset">Asset</option><option value="alert">Alert</option><option value="incident">Incident</option></Select></label>
                            <label className="block space-y-1"><span className="text-xs text-vexus-muted">Evidence target</span><Select value={contextId} onChange={(event) => setContextId(event.target.value)} disabled={loading}>{contextType === "asset" && assets.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}{contextType === "alert" && alerts.map((item) => <option key={item.id} value={item.id}>{item.rule_key} · {item.severity}</option>)}{contextType === "incident" && incidents.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
                            <label className="block space-y-1"><span className="text-xs text-vexus-muted">Question</span><textarea value={question} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setQuestion(event.target.value)} rows={5} placeholder="Ask about this observed evidence..." className="w-full resize-y rounded border border-vexus-border bg-vexus-bg px-2.5 py-2 text-sm text-vexus-text placeholder:text-vexus-muted/60 focus:outline-none focus:ring-1 focus:ring-vexus-accent" /></label>
                            <Button type="submit" disabled={asking || !contextId || !status?.configured}>{asking ? "Analyzing..." : "Ask AI"}</Button>
                        </form>
                    </Card>

                    <Card className="p-5">
                        <div className="mb-4 flex items-start justify-between gap-4"><div><h2 className="text-sm font-medium text-white">Analysis</h2><p className="mt-1 text-xs text-vexus-muted">{selectedLabel || "Choose an evidence target"}</p></div>{answer && <span className="text-xs text-vexus-muted">{(answer.confidence * 100).toFixed(0)}% confidence</span>}</div>
                        {!answer && <div className="flex min-h-56 items-center justify-center border border-dashed border-vexus-border text-center text-sm text-vexus-muted">Ask a grounded question to begin.</div>}
                        {answer && <div className="space-y-4">{SECTIONS.map(([key, label, color]) => { const items = answer[key] as string[]; return items.length ? <section key={key}><h3 className="mb-1 text-xs font-medium text-vexus-muted">{label}</h3><ul className={`space-y-1 text-sm ${color}`}>{items.map((item, index) => <li key={index}>• {item}</li>)}</ul></section> : null; })}<div className="border-t border-vexus-border pt-2 text-xs text-vexus-muted">Provider: {answer.provider} · {new Date(answer.created_at).toLocaleString()}</div></div>}
                    </Card>
                </div>

                {history.length > 0 && <Card className="p-5"><h2 className="mb-3 text-sm font-medium text-white">Recent questions for this context</h2><div className="space-y-2">{history.slice(0, 5).map((item) => <button key={item.id} type="button" onClick={() => setAnswer(item)} className="block w-full rounded border border-vexus-border px-3 py-2 text-left text-xs text-vexus-muted hover:border-vexus-accent hover:text-vexus-text">{item.question || item.query_type} <span className="float-right">{new Date(item.created_at).toLocaleString()}</span></button>)}</div></Card>}
            </div>
        </Layout>
    );
}
