import { HTMLAttributes } from "react";

export default function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`bg-vexus-panel border border-vexus-border rounded-lg ${className}`}
      {...props}
    />
  );
}
