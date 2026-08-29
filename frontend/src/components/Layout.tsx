import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/assets", label: "Assets" },
  { to: "/alerts", label: "Alerts" },
  { to: "/incidents", label: "Incidents" },
  { to: "/discovery", label: "Discovery" },
  { to: "/topology", label: "Topology" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-vexus-bg text-vexus-text">
      <div className="border-b border-vexus-border">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-sm font-semibold tracking-tight">VEXUS</span>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `text-xs rounded px-2.5 py-1.5 transition-colors ${
                      isActive
                        ? "bg-vexus-accent/20 text-vexus-accent"
                        : "text-vexus-muted hover:text-vexus-text hover:bg-vexus-border/40"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-vexus-muted">
              {user?.username} · {user?.role.replace("_", " ")}
            </span>
            {user?.role === "admin" && (
              <button
                onClick={() => navigate("/admin")}
                className="text-xs text-red-400 hover:text-red-300 border border-red-900 rounded px-2.5 py-1.5"
              >
                Admin Panel
              </button>
            )}
            <button
              onClick={handleLogout}
              className="text-xs text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
      <div className="max-w-6xl mx-auto px-6 py-6">{children}</div>
    </div>
  );
}
