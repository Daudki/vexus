import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-black text-vexus-text">
      <div className="border-b border-red-900/50 bg-red-950/10">
        <div className="max-w-5xl mx-auto px-3 sm:px-4 lg:px-6 py-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[11px] font-semibold tracking-wider text-red-400 border border-red-900 rounded px-2 py-0.5 sm:text-xs">
                ADMIN PANEL
              </span>
              <span className="text-sm text-vexus-muted">VEXUS</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <button
                onClick={() => navigate("/dashboard")}
                className="text-[11px] text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5 sm:text-xs"
              >
                ← Back to dashboard
              </button>
              <span className="text-[11px] text-vexus-muted sm:text-xs">{user?.username}</span>
              <button
                onClick={handleLogout}
                className="text-[11px] text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5 sm:text-xs"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="max-w-5xl mx-auto px-3 sm:px-4 lg:px-6 py-4 sm:py-6">{children}</div>
    </div>
  );
}
