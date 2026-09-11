import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import Footer from "./Footer";
import Brand from "./Brand";
import { useAuth } from "../hooks/useAuth";
import AIChatbot from "./AIChatbot";

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
  const [aiOpen, setAIOpen] = useState(false);

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
              <Brand compact />
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
                    {item.to === "/ai" && <img src="/vexusAI.png" alt="" className="mr-1 inline-block h-5 w-5 rounded object-cover align-middle" />}
                    {item.label}
                  </NavLink>
                ))}
                <button
                  type="button"
                  onClick={() => setAIOpen(true)}
                  className="rounded px-2.5 py-1.5 text-xs text-vexus-muted transition-colors hover:bg-vexus-border/40 hover:text-vexus-text"
                >
                  <img src="/vexusAI.png" alt="" className="mr-1 inline-block h-5 w-5 rounded object-cover align-middle" />
                  AI Assistant
                </button>
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

      <button
        type="button"
        onClick={() => setAIOpen(true)}
        className="fixed bottom-5 right-5 z-40 flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border border-vexus-accent/70 bg-vexus-bg shadow-lg shadow-blue-950/50 transition-transform hover:scale-105"
        aria-label="Open AI Assistant"
        title="Open AI Assistant"
      >
        <img src="/vexusAI.png" alt="" className="h-full w-full object-cover" />
      </button>

      <AIChatbot open={aiOpen} onClose={() => setAIOpen(false)} />

      <Footer />
    </div>
  );
}
