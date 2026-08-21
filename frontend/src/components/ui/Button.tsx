import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-vexus-accent hover:bg-blue-600 text-white",
  secondary: "border border-vexus-border text-vexus-text hover:bg-vexus-border/40",
  danger: "bg-red-900/40 border border-red-800 text-red-300 hover:bg-red-900/60",
  ghost: "text-vexus-muted hover:text-vexus-text",
};

export default function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`text-xs font-medium rounded px-3 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
