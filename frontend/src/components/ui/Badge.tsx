const PALETTE: Record<string, string> = {
  // asset status
  online: "text-green-400 bg-green-950/40 border-green-900",
  offline: "text-red-400 bg-red-950/40 border-red-900",
  unknown: "text-vexus-muted bg-vexus-bg border-vexus-border",

  // trust status
  trusted: "text-green-400 bg-green-950/40 border-green-900",
  untrusted: "text-red-400 bg-red-950/40 border-red-900",

  // criticality
  low: "text-vexus-muted bg-vexus-bg border-vexus-border",
  medium: "text-yellow-400 bg-yellow-950/40 border-yellow-900",
  high: "text-orange-400 bg-orange-950/40 border-orange-900",
  critical: "text-red-400 bg-red-950/40 border-red-900",

  // relationship confidence
  confirmed: "text-green-400 bg-green-950/40 border-green-900",
  inferred: "text-blue-400 bg-blue-950/40 border-blue-900",

  // scan status
  completed: "text-green-400 bg-green-950/40 border-green-900",
  running: "text-blue-400 bg-blue-950/40 border-blue-900",
  failed: "text-red-400 bg-red-950/40 border-red-900",
  refused: "text-yellow-400 bg-yellow-950/40 border-yellow-900",

  // alert status
  new: "text-blue-400 bg-blue-950/40 border-blue-900",
  acknowledged: "text-yellow-400 bg-yellow-950/40 border-yellow-900",
  investigating: "text-orange-400 bg-orange-950/40 border-orange-900",
  resolved: "text-green-400 bg-green-950/40 border-green-900",
  false_positive: "text-vexus-muted bg-vexus-bg border-vexus-border",
  closed: "text-vexus-muted bg-vexus-bg border-vexus-border",

  // severity
  informational: "text-vexus-muted bg-vexus-bg border-vexus-border",

  // user roles
  admin: "text-red-400 bg-red-950/40 border-red-900",
  security_analyst: "text-blue-400 bg-blue-950/40 border-blue-900",
  network_administrator: "text-purple-400 bg-purple-950/40 border-purple-900",
  viewer: "text-vexus-muted bg-vexus-bg border-vexus-border",

  // system / provider health
  healthy: "text-green-400 bg-green-950/40 border-green-900",
  unhealthy: "text-red-400 bg-red-950/40 border-red-900",
  degraded: "text-yellow-400 bg-yellow-950/40 border-yellow-900",
  configured: "text-green-400 bg-green-950/40 border-green-900",
  disabled: "text-vexus-muted bg-vexus-bg border-vexus-border",
};

const DEFAULT = "text-vexus-muted bg-vexus-bg border-vexus-border";

export default function Badge({ value }: { value: string }) {
  const style = PALETTE[value] ?? DEFAULT;
  return (
    <span className={`text-xs border rounded px-2 py-0.5 whitespace-nowrap ${style}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}
