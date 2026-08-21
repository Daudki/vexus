interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  unit?: string;
}

export default function Sparkline({ values, width = 480, height = 80, color = "#3b82f6", unit = "" }: SparklineProps) {
  if (values.length === 0) {
    return <div className="text-xs text-vexus-muted py-6 text-center">No samples yet.</div>;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const padding = 8;

  const points = values.map((v, i) => {
    const x = padding + (i / Math.max(values.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((v - min) / range) * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth={2} />
      </svg>
      <div className="flex justify-between text-xs text-vexus-muted mt-1">
        <span>min {min.toFixed(1)}{unit}</span>
        <span>max {max.toFixed(1)}{unit}</span>
        <span>latest {values[0].toFixed(1)}{unit}</span>
      </div>
    </div>
  );
}
