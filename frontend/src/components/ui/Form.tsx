import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

interface FieldProps {
  label?: string;
  children: ReactNode;
}

export function Field({ label, children }: FieldProps) {
  return (
    <div className="space-y-1">
      {label && <label className="text-xs text-vexus-muted">{label}</label>}
      {children}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full bg-vexus-bg border border-vexus-border rounded px-2.5 py-1.5 text-sm text-vexus-text placeholder:text-vexus-muted/60 focus:outline-none focus:ring-1 focus:ring-vexus-accent ${props.className ?? ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full bg-vexus-bg border border-vexus-border rounded px-2.5 py-1.5 text-sm text-vexus-text focus:outline-none focus:ring-1 focus:ring-vexus-accent ${props.className ?? ""}`}
    />
  );
}
