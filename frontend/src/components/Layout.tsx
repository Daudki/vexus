import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Footer from "./Footer";
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
    <div className="flex min-h-screen flex-col bg-vexus-bg text-vexus-text">
      <header className="sticky top-0 z-50 border-b border-vexus-border/80 bg-vexus-bg/80 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-3 py-3 sm:px-4 lg:px-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4 lg:gap-6">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md border border-vexus-accent/60 bg-vexus-accent/10 text-[10px] font-bold tracking-[0.22em] text-vexus-accent">
                  V
                </div>
                <span className="text-sm font-semibold tracking-[0.22em]">VEXUS</span>
              </div>
              <nav className="flex flex-wrap items-center gap-1">
                {NAV_ITEMS.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `rounded px-2.5 py-1.5 text-xs transition-colors ${isActive
                        ? "bg-vexus-accent/20 text-vexus-accent"
                        : "text-vexus-muted hover:bg-vexus-border/40 hover:text-vexus-text"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <span className="text-[11px] text-vexus-muted sm:text-xs">
                {user?.username} · {user?.role.replace("_", " ")}
              </span>
              {user?.role === "admin" && (
                <button
                  onClick={() => navigate("/admin")}
                  className="rounded border border-red-900/80 px-2.5 py-1.5 text-[11px] text-red-400 transition-colors hover:text-red-300"
                >
                  Admin Panel
                </button>
              )}
              <button
                onClick={handleLogout}
                className="rounded border border-vexus-border px-2.5 py-1.5 text-[11px] text-vexus-muted transition-colors hover:text-vexus-text"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-3 py-4 sm:px-4 sm:py-6 lg:px-6">{children}</main>

      <Footer />
    </div>
  );
}
