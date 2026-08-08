import { ReactNode } from "react";

export function StatCard({ label, value, accent, icon }: { label: string; value: ReactNode; accent?: string; icon?: ReactNode }) {
  return (
    <div className="card p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-ink-300 text-sm">{label}</span>
        {icon}
      </div>
      <span className={`mono-stat text-3xl font-semibold ${accent || "text-ink-100"}`}>{value}</span>
    </div>
  );
}
