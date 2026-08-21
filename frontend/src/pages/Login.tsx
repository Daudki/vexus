import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-vexus-bg">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-vexus-panel border border-vexus-border rounded-lg p-8 space-y-5"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight">VEXUS</h1>
          <p className="text-sm text-vexus-muted">Network Security Intelligence Platform</p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">
            {error}
          </div>
        )}

        <div className="space-y-1">
          <label className="text-sm text-vexus-muted" htmlFor="username">Username</label>
          <input
            id="username"
            className="w-full bg-vexus-bg border border-vexus-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-vexus-accent"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm text-vexus-muted" htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            className="w-full bg-vexus-bg border border-vexus-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-vexus-accent"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-vexus-accent hover:bg-blue-600 disabled:opacity-50 text-white text-sm font-medium rounded px-3 py-2 transition-colors"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
