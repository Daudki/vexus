import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Card from "./ui/Card";
import { TopRiskAsset, getTopRiskAssets } from "../services/risk";

function levelForScore(score: number): string {
  if (score >= 70) return "critical";
  if (score >= 45) return "high";
  if (score >= 20) return "medium";
  return "low";
}

const LEVEL_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-vexus-muted",
};

export default function TopRisksPanel() {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<TopRiskAsset[] | null>(null);

  useEffect(() => {
    getTopRiskAssets(5).then(setAssets).catch(() => setAssets(null));
  }, []);

  if (!assets) return null;

  const withScore = assets.filter((a) => a.risk_score > 0);

  return (
    <Card className="p-4">
      <h2 className="text-sm font-medium text-vexus-muted mb-3">Top Risks</h2>
      {withScore.length === 0 ? (
        <p className="text-xs text-vexus-muted">
          No risk scores computed yet. Visit an asset's detail page or trigger a recompute from the Alerts page.
        </p>
      ) : (
        <ul className="space-y-2">
          {withScore.map((asset) => {
            const level = levelForScore(asset.risk_score);
            return (
              <li
                key={asset.id}
                onClick={() => navigate(`/assets/${asset.id}`)}
                className="flex items-center justify-between text-sm cursor-pointer hover:bg-vexus-border/20 rounded px-2 py-1.5 -mx-2"
              >
                <span>{asset.hostname || asset.ip_address || asset.id}</span>
                <span className={`text-xs font-medium ${LEVEL_COLOR[level]}`}>
                  {asset.risk_score.toFixed(0)} · {level}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
