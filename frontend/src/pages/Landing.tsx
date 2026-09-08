import { useNavigate } from "react-router-dom";
import Footer from "../components/Footer";

const FEATURE_CARDS = [
  { title: "Asset visibility", detail: "Map every system, service, and dependency in one view." },
  { title: "Threat detection", detail: "Correlate advisory signals, alerts, and asset risk in real time." },
  { title: "Incident response", detail: "Move from detection to action with prioritized investigation paths." },
];

const PLATFORM_STATS = [
  { value: "24/7", label: "signal coverage" },
  { value: "3x", label: "faster triage" },
  { value: "99.9%", label: "platform uptime" },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-vexus-bg text-vexus-text">
      <header className="sticky top-0 z-50 border-b border-vexus-border/80 bg-vexus-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-vexus-accent/60 bg-vexus-accent/10 text-[10px] font-bold tracking-[0.24em] text-vexus-accent">
              V
            </div>
            <span className="text-sm font-semibold tracking-[0.22em]">VEXUS</span>
          </div>

          <nav className="hidden items-center gap-6 text-sm text-vexus-muted md:flex">
            <a href="#platform" className="transition-colors hover:text-vexus-text">Platform</a>
            <a href="#features" className="transition-colors hover:text-vexus-text">Features</a>
            <a href="#security" className="transition-colors hover:text-vexus-text">Security</a>
          </nav>

          <button
            type="button"
            onClick={() => navigate("/login")}
            className="rounded border border-vexus-border px-3 py-1.5 text-sm text-vexus-text transition-colors hover:border-vexus-accent hover:text-vexus-accent"
          >
            Sign in
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-14 pt-10 sm:px-6 lg:px-8">
        <section className="grid items-center gap-10 py-8 lg:grid-cols-2 lg:py-14">
          <div className="space-y-8">
            <div className="inline-flex items-center rounded-full border border-vexus-accent/40 bg-vexus-accent/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-vexus-accent">
              Security intelligence
            </div>

            <div className="space-y-4">
              <h1 className="max-w-xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                See the network before threats do.
              </h1>
              <p className="max-w-xl text-base text-vexus-muted sm:text-lg">
                VEXUS gives security teams unified visibility across assets, detections, and active incidents so they can act faster and with more confidence.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="rounded bg-vexus-accent px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              >
                Launch platform
              </button>
              <button
                type="button"
                onClick={() => navigate("/dashboard")}
                className="rounded border border-vexus-border bg-vexus-panel/80 px-5 py-3 text-sm font-medium text-vexus-text transition-colors hover:border-vexus-accent/60"
              >
                View dashboard
              </button>
            </div>

            <div id="platform" className="grid gap-4 pt-3 sm:grid-cols-3">
              {PLATFORM_STATS.map((stat) => (
                <div key={stat.label} className="rounded-xl border border-vexus-border bg-vexus-panel/60 p-4">
                  <div className="text-2xl font-semibold text-white">{stat.value}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.14em] text-vexus-muted">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-vexus-border bg-gradient-to-br from-vexus-accent/10 to-transparent p-8 shadow-2xl shadow-blue-950/20">
            <div className="flex flex-col gap-6">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-vexus-muted">Unified visibility</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">See everything at a glance</h2>
              </div>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-vexus-accent/20 text-vexus-accent">
                    ✓
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">Real-time asset discovery</p>
                    <p className="mt-0.5 text-xs text-vexus-muted">Automatically identify and track every device on your network</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-vexus-accent/20 text-vexus-accent">
                    ✓
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">Threat correlations</p>
                    <p className="mt-0.5 text-xs text-vexus-muted">Connect alerts, advisories, and asset context instantly</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-vexus-accent/20 text-vexus-accent">
                    ✓
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">Guided response</p>
                    <p className="mt-0.5 text-xs text-vexus-muted">Get prioritized actions tailored to your environment</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="space-y-5 py-8">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-vexus-muted">Built for operators</p>
              <h2 className="mt-2 text-3xl font-semibold text-white">Everything needed to respond with clarity.</h2>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {FEATURE_CARDS.map((feature) => (
              <div key={feature.title} className="rounded-2xl border border-vexus-border bg-vexus-panel/60 p-5 transition-colors hover:border-vexus-accent/30">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg border border-vexus-accent/30 bg-vexus-accent/10 text-vexus-accent">
                  •
                </div>
                <h3 className="text-lg font-medium text-white">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-vexus-muted">{feature.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="security" className="py-8">
          <div className="rounded-2xl border border-vexus-border bg-gradient-to-r from-vexus-panel/90 to-vexus-accent/5 p-6 sm:p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-vexus-muted">Operational confidence</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">Security teams need visibility, not noise.</h3>
              </div>
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="rounded border border-vexus-accent/40 bg-vexus-accent/10 px-4 py-2.5 text-sm font-medium text-vexus-accent transition-colors hover:bg-vexus-accent/20"
              >
                Get started
              </button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
