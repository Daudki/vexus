import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import HealthStrip from "../components/HealthStrip";
import NetworkHealthPanel from "../components/NetworkHealthPanel";
import TopRisksPanel from "../components/TopRisksPanel";
import Card from "../components/ui/Card";

const TILES = [
  { to: "/assets", title: "Assets", description: "Search, filter, and edit the asset inventory." },
  { to: "/alerts", title: "Alerts", description: "Review detections, manage status, tune detection rules." },
  { to: "/incidents", title: "Incidents", description: "Investigate incidents built from linked evidence." },
  { to: "/discovery", title: "Discovery", description: "Trigger authorized scans and review scan history." },
  { to: "/topology", title: "Topology", description: "Manual and inferred relationships between assets." },
];

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <Layout>
      <div className="space-y-6">
        <HealthStrip />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <NetworkHealthPanel />
          <TopRisksPanel />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {TILES.map((tile) => (
            <Card
              key={tile.to}
              className="p-4 cursor-pointer hover:border-vexus-accent transition-colors"
              onClick={() => navigate(tile.to)}
            >
              <h2 className="text-sm font-medium">{tile.title}</h2>
              <p className="text-xs text-vexus-muted mt-1">{tile.description}</p>
            </Card>
          ))}
        </div>
      </div>
    </Layout>
  );
}
