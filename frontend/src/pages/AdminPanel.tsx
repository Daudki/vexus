import { useEffect, useState } from "react";
import AdminLayout from "../components/AdminLayout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { AuditLogEntry, listAuditLogs } from "../services/audit";
import {
  AdminUser,
  Role,
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  setUserActive,
  updateUserRole,
} from "../services/users";
import { getScanRanges, updateScanRanges } from "../services/admin";

const ROLES: Role[] = ["admin", "security_analyst", "network_administrator", "viewer"];

type Tab = "users" | "audit";

export default function AdminPanel() {
  const { user: me } = useAuth();
  const [tab, setTab] = useState<Tab>("users");

  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [scanRanges, setScanRanges] = useState<string[]>([]);
  const [rangeDraft, setRangeDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [creating, setCreating] = useState(false);

  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetting, setResetting] = useState(false);

  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [usersData, rangesData] = await Promise.all([listUsers(), getScanRanges()]);
      setUsers(usersData);
      setScanRanges(rangesData.ranges);
      setRangeDraft(rangesData.ranges.join(", "));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load admin settings.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setCreating(true);
    try {
      await createUser({ username, email, password, role });
      setUsername("");
      setEmail("");
      setPassword("");
      setRole("viewer");
      setNotice(`User '${username}' created.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create user.");
    } finally {
      setCreating(false);
    }
  }

  async function handleRoleChange(userId: string, newRole: Role) {
    setError(null);
    setBusyUserId(userId);
    try {
      await updateUserRole(userId, newRole);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update role.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleToggleActive(u: AdminUser) {
    setError(null);
    setBusyUserId(u.id);
    try {
      await setUserActive(u.id, !u.is_active);
      setNotice(`User '${u.username}' ${u.is_active ? "deactivated" : "reactivated"}.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update user status.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleDelete(u: AdminUser) {
    if (!window.confirm(`Permanently delete user '${u.username}'? This cannot be undone.`)) return;
    setError(null);
    setBusyUserId(u.id);
    try {
      await deleteUser(u.id);
      setNotice(`User '${u.username}' deleted.`);
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to delete user."
      );
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!resetTarget) return;
    setError(null);
    setResetting(true);
    try {
      await resetUserPassword(resetTarget.id, resetPassword);
      setNotice(`Password reset for '${resetTarget.username}'.`);
      setResetTarget(null);
      setResetPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reset password.");
    } finally {
      setResetting(false);
    }
  }

  async function handleSaveScanRanges(e: React.FormEvent) {
    e.preventDefault();
    const nextRanges = rangeDraft
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean);

    setError(null);
    try {
      const updated = await updateScanRanges(nextRanges);
      setScanRanges(updated.ranges);
      setRangeDraft(updated.ranges.join(", "));
      setNotice("Authorized scan ranges updated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update scan ranges.");
    }
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Admin</h1>
            <p className="text-xs text-vexus-muted mt-1">
              Manage accounts and roles, or review the audit log. Every action here is written to the audit log.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant={tab === "users" ? "primary" : "secondary"} onClick={() => setTab("users")}>
              User management
            </Button>
            <Button variant={tab === "audit" ? "primary" : "secondary"} onClick={() => setTab("audit")}>
              Audit log
            </Button>
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}
        {notice && (
          <div className="text-sm text-blue-300 bg-blue-950/40 border border-blue-900 rounded px-3 py-2">{notice}</div>
        )}

        {tab === "users" ? (
          <>
            <Card className="p-4">
              <h2 className="text-sm font-medium text-vexus-muted mb-3">Authorized scan ranges</h2>
              <form onSubmit={handleSaveScanRanges} className="space-y-3">
                <Field label="CIDR ranges (comma-separated)">
                  <Input
                    value={rangeDraft}
                    onChange={(e) => setRangeDraft(e.target.value)}
                    placeholder="10.0.0.0/8, 192.168.1.0/24"
                  />
                </Field>
                <div className="flex items-center gap-2">
                  <Button type="submit">Save ranges</Button>
                  <span className="text-[11px] text-vexus-muted">
                    {scanRanges.length ? scanRanges.join(", ") : "No ranges configured"}
                  </span>
                </div>
              </form>
            </Card>

            <Card className="p-4">
              <h2 className="text-sm font-medium text-vexus-muted mb-3">Create user</h2>
              <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
                <Field label="Username">
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
                </Field>
                <Field label="Email">
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                </Field>
                <Field label="Password">
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </Field>
                <Field label="Role">
                  <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.replace(/_/g, " ")}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Button type="submit" disabled={creating}>
                  {creating ? "Creating…" : "Create"}
                </Button>
              </form>
              <p className="text-[11px] text-vexus-muted mt-2">
                Password must be 8+ characters with an uppercase letter, lowercase letter, digit, and symbol.
              </p>
            </Card>

            <Card className="overflow-hidden">
              <table className="w-full text-sm">
                <thead className="text-xs text-vexus-muted border-b border-vexus-border">
                  <tr>
                    <th className="text-left px-4 py-2">Username</th>
                    <th className="text-left px-4 py-2">Email</th>
                    <th className="text-left px-4 py-2">Role</th>
                    <th className="text-left px-4 py-2">Status</th>
                    <th className="text-left px-4 py-2">Last login</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users === null && (
                    <tr>
                      <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                        Loading…
                      </td>
                    </tr>
                  )}
                  {users?.map((u) => {
                    const isSelf = u.id === me?.id;
                    const busy = busyUserId === u.id;
                    return (
                      <tr key={u.id} className="border-b border-vexus-border last:border-0 align-top">
                        <td className="px-4 py-2">
                          {u.username}
                          {isSelf && <span className="text-vexus-muted"> (you)</span>}
                        </td>
                        <td className="px-4 py-2 text-vexus-muted">{u.email}</td>
                        <td className="px-4 py-2">
                          <Select
                            value={u.role}
                            onChange={(e) => handleRoleChange(u.id, e.target.value as Role)}
                            className="text-xs"
                            disabled={busy}
                          >
                            {ROLES.map((r) => (
                              <option key={r} value={r}>
                                {r.replace(/_/g, " ")}
                              </option>
                            ))}
                          </Select>
                        </td>
                        <td className="px-4 py-2">
                          <Badge value={u.is_active ? "online" : "offline"} />
                        </td>
                        <td className="px-4 py-2 text-xs text-vexus-muted">
                          {u.last_login ? new Date(u.last_login).toLocaleString() : "Never"}
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-1.5">
                            <Button
                              variant="secondary"
                              disabled={busy || isSelf}
                              onClick={() => handleToggleActive(u)}
                              title={isSelf ? "You cannot deactivate your own account." : undefined}
                            >
                              {u.is_active ? "Deactivate" : "Reactivate"}
                            </Button>
                            <Button
                              variant="secondary"
                              disabled={busy}
                              onClick={() => {
                                setResetTarget(u);
                                setResetPassword("");
                              }}
                            >
                              Reset password
                            </Button>
                            <Button
                              variant="danger"
                              disabled={busy || isSelf}
                              onClick={() => handleDelete(u)}
                              title={isSelf ? "You cannot delete your own account." : undefined}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>

            {resetTarget && (
              <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
                <Card className="p-4 w-full max-w-sm">
                  <h2 className="text-sm font-medium mb-3">Reset password for '{resetTarget.username}'</h2>
                  <form onSubmit={handleResetPassword} className="space-y-3">
                    <Field label="New password">
                      <Input
                        type="password"
                        value={resetPassword}
                        onChange={(e) => setResetPassword(e.target.value)}
                        required
                        minLength={8}
                        autoFocus
                      />
                    </Field>
                    <p className="text-[11px] text-vexus-muted">
                      8+ characters, with an uppercase letter, lowercase letter, digit, and symbol. Share the
                      new password with the user directly — this isn't emailed to them.
                    </p>
                    <div className="flex justify-end gap-2 pt-1">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => {
                          setResetTarget(null);
                          setResetPassword("");
                        }}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" disabled={resetting}>
                        {resetting ? "Resetting…" : "Reset password"}
                      </Button>
                    </div>
                  </form>
                </Card>
              </div>
            )}
          </>
        ) : (
          <AuditLogPanel />
        )}
      </div>
    </AdminLayout>
  );
}

function AuditLogPanel() {
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState("");

  async function load(action?: string) {
    setError(null);
    try {
      setEntries(await listAuditLogs(action ? { action } : {}));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load audit log.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilter(e: React.FormEvent) {
    e.preventDefault();
    load(actionFilter.trim() || undefined);
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
      )}

      <Card className="p-4">
        <form onSubmit={handleFilter} className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1 min-w-0">
            <Field label="Filter by action (e.g. user.delete, login)">
              <Input
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                placeholder="Leave blank to show everything"
              />
            </Field>
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit">Filter</Button>
            {actionFilter && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setActionFilter("");
                  load();
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </form>
      </Card>

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="text-xs text-vexus-muted border-b border-vexus-border">
            <tr>
              <th className="text-left px-4 py-2">Time</th>
              <th className="text-left px-4 py-2">Actor</th>
              <th className="text-left px-4 py-2">Action</th>
              <th className="text-left px-4 py-2">Target</th>
              <th className="text-left px-4 py-2">Detail</th>
              <th className="text-left px-4 py-2">IP</th>
              <th className="text-left px-4 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {entries === null && (
              <tr>
                <td colSpan={7} className="text-center text-vexus-muted text-xs py-6">
                  Loading…
                </td>
              </tr>
            )}
            {entries?.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-vexus-muted text-xs py-6">
                  No matching entries.
                </td>
              </tr>
            )}
            {entries?.map((e) => (
              <tr key={e.id} className="border-b border-vexus-border last:border-0 align-top">
                <td className="px-4 py-2 text-xs text-vexus-muted whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2">{e.actor_username}</td>
                <td className="px-4 py-2">
                  <Badge value={e.success ? "resolved" : "failed"} />
                  <span className="ml-2">{e.action}</span>
                </td>
                <td className="px-4 py-2 text-xs text-vexus-muted">
                  {e.target_type}
                  {e.target_id ? `:${e.target_id.slice(0, 8)}` : ""}
                </td>
                <td className="px-4 py-2 text-xs text-vexus-muted max-w-[18rem] break-words" title={e.detail}>
                  {e.detail}
                </td>
                <td className="px-4 py-2 text-xs text-vexus-muted whitespace-nowrap">{e.ip_address}</td>
                <td className="px-4 py-2">
                  <Badge value={e.success ? "trusted" : "untrusted"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
