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
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold tracking-wider text-red-400 border border-red-900 rounded px-2 py-0.5">
              ADMIN PANEL
            </span>
            <span className="text-sm text-vexus-muted">VEXUS</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/dashboard")}
              className="text-xs text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5"
            >
              ← Back to dashboard
            </button>
            <span className="text-xs text-vexus-muted">{user?.username}</span>
            <button
              onClick={handleLogout}
              className="text-xs text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
      <div className="max-w-5xl mx-auto px-6 py-6">{children}</div>
    </div>
  );
}
