import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import Footer from "./Footer";
import { useAuth } from "../hooks/useAuth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-vexus-bg text-vexus-text">
      <header className="sticky top-0 z-50 border-b border-red-900/50 bg-red-950/10 backdrop-blur-xl">
        <div className="mx-auto max-w-5xl px-3 py-3 sm:px-4 lg:px-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded border border-red-900 px-2 py-0.5 text-[11px] font-semibold tracking-[0.2em] text-red-400 sm:text-xs">
                ADMIN PANEL
              </span>
              <span className="text-sm text-vexus-muted">VEXUS</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <button
                onClick={() => navigate("/dashboard")}
                className="rounded border border-vexus-border px-2.5 py-1.5 text-[11px] text-vexus-muted transition-colors hover:text-vexus-text sm:text-xs"
              >
                ← Back to dashboard
              </button>
              <span className="text-[11px] text-vexus-muted sm:text-xs">{user?.username}</span>
              <button
                onClick={handleLogout}
                className="rounded border border-vexus-border px-2.5 py-1.5 text-[11px] text-vexus-muted transition-colors hover:text-vexus-text sm:text-xs"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-3 py-4 sm:px-4 sm:py-6 lg:px-6">{children}</main>

      <Footer />
    </div>
  );
}
