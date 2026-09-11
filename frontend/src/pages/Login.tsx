import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Footer from "../components/Footer";
import Brand from "../components/Brand";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [capsLockActive, setCapsLockActive] = useState(false);

  useEffect(() => {
    if (user) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please check your credentials.");
    } finally {
      setSubmitting(false);
    }
  }

  const handlePasswordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const capsLockOn = e.getModifierState("CapsLock");
    setCapsLockActive(capsLockOn);
  };

  const handlePasswordKeyUp = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const capsLockOn = e.getModifierState("CapsLock");
    setCapsLockActive(capsLockOn);
  };

  const isFormValid = username.trim() && password.length >= 6;

  return (
    <div className="flex min-h-screen flex-col bg-vexus-bg text-vexus-text">
      <header className="sticky top-0 z-50 border-b border-vexus-border/80 bg-vexus-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="flex items-center gap-3 transition-opacity hover:opacity-80"
          >
            <Brand compact />
          </button>

          <button
            type="button"
            onClick={() => navigate("/")}
            className="rounded border border-vexus-border px-3 py-1.5 text-sm text-vexus-text transition-colors hover:border-vexus-accent hover:text-vexus-accent"
          >
            Back
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-md flex-1 px-4 py-12 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-vexus-border bg-vexus-panel/80 p-8 shadow-2xl shadow-blue-950/20">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-vexus-muted">Welcome back</p>
              <h1 className="mt-3 text-3xl font-semibold text-white">Sign in</h1>
            </div>
            <div className="rounded-full border border-vexus-accent/30 bg-vexus-accent/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-vexus-accent">
              Secure
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="flex items-start gap-3 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
                <div className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-red-900/50 text-[10px] font-bold">!</div>
                <div className="flex-1">
                  <p className="font-medium">Authentication failed</p>
                  <p className="mt-0.5 text-red-300/80">{error}</p>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium text-vexus-muted">
                Username or Email
              </label>
              <input
                id="username"
                className="w-full rounded border border-vexus-border bg-vexus-bg px-4 py-3 text-sm text-vexus-text placeholder:text-vexus-muted/50 transition-colors focus:border-vexus-accent focus:outline-none focus:ring-1 focus:ring-vexus-accent/20"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="off"
                placeholder="admin"
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-sm font-medium text-vexus-muted">
                  Password
                </label>
                <a href="#" className="text-xs text-vexus-accent transition-colors hover:text-blue-400">
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  className="w-full rounded border border-vexus-border bg-vexus-bg px-4 py-3 text-sm text-vexus-text placeholder:text-vexus-muted/50 transition-colors focus:border-vexus-accent focus:outline-none focus:ring-1 focus:ring-vexus-accent/20"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={handlePasswordKeyDown}
                  onKeyUp={handlePasswordKeyUp}
                  autoComplete="off"
                  placeholder="••••••••"
                  disabled={submitting}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-vexus-muted transition-colors hover:text-vexus-text disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={submitting}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-2.803m5.596-3.856a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M1 1l22 22" />
                    </svg>
                  )}
                </button>
              </div>
              {capsLockActive && (
                <div className="text-xs text-yellow-400">
                  ⚠️ Caps Lock is on
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting || !isFormValid}
              className="w-full rounded bg-vexus-accent px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Signing in…
                </span>
              ) : (
                "Sign in to VEXUS"
              )}
            </button>
          </form>

          <div className="mt-8 border-t border-vexus-border/50 pt-6 text-center text-xs text-vexus-muted">
            <p>On a shared device?{" "}
              <button
                type="button"
                onClick={() => {
                  setUsername("");
                  setPassword("");
                }}
                className="text-vexus-accent transition-colors hover:text-blue-400"
              >
                Clear credentials
              </button>
            </p>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
