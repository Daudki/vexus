import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AIPanel from "../components/AIPanel";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { summarizeIncident } from "../services/ai";
import {
  IncidentDetail as IncidentDetailType,
  Note,
  TimelineEntry,
  addNote,
  getIncident,
  getTimeline,
  listNotes,
  updateIncident,
} from "../services/incidents";

const CAN_MANAGE_ROLES = ["admin", "security_analyst", "network_administrator"];
const STATUS_OPTIONS = ["open", "investigating", "resolved", "false_positive", "closed"];

const KIND_ICON: Record<string, string> = { event: "◆", note: "✎", audit: "⚙" };

export default function IncidentDetail() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [incident, setIncident] = useState<IncidentDetailType | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [newNote, setNewNote] = useState("");
  const [resolution, setResolution] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const canManage = user ? CAN_MANAGE_ROLES.includes(user.role) : false;

  async function load() {
    if (!incidentId) return;
    setError(null);
    try {
      const [incidentData, timelineData, notesData] = await Promise.all([
        getIncident(incidentId),
        getTimeline(incidentId),
        listNotes(incidentId),
      ]);
      setIncident(incidentData);
      setTimeline(timelineData);
      setNotes(notesData);
      setResolution(incidentData.resolution);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incident.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentId]);

  async function handleStatusChange(status: string) {
    if (!incidentId) return;
    setError(null);
    try {
      const updated = await updateIncident(incidentId, { status });
      setIncident(updated);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update status.");
    }
  }

  async function handleSaveResolution() {
    if (!incidentId) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateIncident(incidentId, { resolution });
      setIncident(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save resolution.");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault();
    if (!incidentId || !newNote.trim()) return;
    setError(null);
    try {
      await addNote(incidentId, newNote.trim());
      setNewNote("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add note.");
    }
  }

  if (!incident) {
    return (
      <Layout>
        <div className="text-sm text-vexus-muted">{error || "Loading…"}</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <button onClick={() => navigate("/incidents")} className="text-xs text-vexus-muted hover:text-vexus-text mb-1">
            ← Back to incidents
          </button>
          <h1 className="text-lg font-semibold tracking-tight">{incident.title}</h1>
          <p className="text-sm text-vexus-muted mt-1">{incident.description}</p>
          <div className="flex items-center gap-2 mt-2">
            <Badge value={incident.severity} />
            <Badge value={incident.status} />
            <span className="text-xs text-vexus-muted">{(incident.confidence * 100).toFixed(0)}% confidence</span>
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-4 space-y-2">
            <h2 className="text-sm font-medium text-vexus-muted">Linked evidence</h2>
            <div className="text-sm">
              <div>{incident.alert_ids.length} alert(s) linked</div>
              <div>{incident.asset_ids.length} affected asset(s)</div>
            </div>
          </Card>

          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-medium text-vexus-muted">Status</h2>
            {canManage ? (
              <Field label="Change status">
                <Select value={incident.status} onChange={(e) => handleStatusChange(e.target.value)}>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <p className="text-xs text-vexus-muted">Your role can view but not change status.</p>
            )}
          </Card>
        </div>

        {incidentId && (
          <AIPanel
            targetType="incident"
            targetId={incidentId}
            canRequest={canManage}
            requestLabel="Summarize incident"
            onRequest={() => summarizeIncident(incidentId)}
          />
        )}

        <Card className="p-4 space-y-3">
          <h2 className="text-sm font-medium text-vexus-muted">Resolution</h2>
          <textarea
            className="w-full bg-vexus-bg border border-vexus-border rounded px-2.5 py-1.5 text-sm min-h-20"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            disabled={!canManage}
            placeholder="Document how this incident was resolved…"
          />
          {canManage && (
            <Button onClick={handleSaveResolution} disabled={saving} variant="secondary">
              {saving ? "Saving…" : "Save resolution"}
            </Button>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-medium text-vexus-muted mb-3">Timeline</h2>
          {timeline.length === 0 && <p className="text-xs text-vexus-muted">No timeline entries yet.</p>}
          <ul className="space-y-3">
            {timeline.map((entry, i) => (
              <li key={i} className="text-sm border-l-2 border-vexus-border pl-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-vexus-muted">{KIND_ICON[entry.kind]}</span>
                  <span>{entry.summary}</span>
                  <span className="text-xs text-vexus-muted ml-auto">
                    {new Date(entry.timestamp).toLocaleString()}
                  </span>
                </div>
                {entry.detail && <div className="text-xs text-vexus-muted mt-0.5">{entry.detail}</div>}
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4 space-y-3">
          <h2 className="text-sm font-medium text-vexus-muted">Investigation notes</h2>
          {notes.length === 0 && <p className="text-xs text-vexus-muted">No notes yet.</p>}
          <ul className="space-y-2">
            {notes.map((note) => (
              <li key={note.id} className="text-sm border-b border-vexus-border last:border-0 pb-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-vexus-muted">{note.author_username}</span>
                  <span className="text-xs text-vexus-muted">{new Date(note.created_at).toLocaleString()}</span>
                </div>
                <div>{note.content}</div>
              </li>
            ))}
          </ul>
          {canManage && (
            <form onSubmit={handleAddNote} className="flex gap-2">
              <input
                className="flex-1 bg-vexus-bg border border-vexus-border rounded px-2.5 py-1.5 text-sm"
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Add an investigation note…"
              />
              <Button type="submit">Add</Button>
            </form>
          )}
        </Card>
      </div>
    </Layout>
  );
}
