import { Link } from "react-router-dom";
import Brand from "./Brand";

const LINKS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/assets", label: "Assets" },
  { to: "/alerts", label: "Alerts" },
  { to: "/incidents", label: "Incidents" },
];

export default function Footer() {
  return (
    <footer className="border-t border-vexus-border/80 bg-vexus-panel/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div>
          <Brand compact />
          <p className="mt-1 text-xs text-vexus-muted">
            Detect faster. Prioritize smarter. Respond with confidence.
          </p>
        </div>

        <nav className="flex flex-wrap items-center gap-3 text-xs text-vexus-muted">
          {LINKS.map((link) => (
            <Link key={link.to} to={link.to} className="transition-colors hover:text-vexus-text">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="text-xs text-vexus-muted">© 2026 VEXUS Security</div>
      </div>
    </footer>
  );
}
