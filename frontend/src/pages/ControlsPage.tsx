import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { Skeleton } from "../components/Skeleton";

interface ControlItem {
  id: string;
  rule_id: string;
  title: string;
  severity: string;
  category: string;
}

async function listControls(params: Record<string, string>) {
  const { data } = await apiClient.get("/controls", { params });
  return data as { items: ControlItem[]; total: number; pages: number };
}

export function ControlsPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["controls", search],
    queryFn: () => listControls(search ? { search } : {}),
  });

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-100">Control Catalog</h1>
        <p className="text-ink-500 text-sm mt-1">Every CIS control observed across all scans, with remediation guidance.</p>
      </div>

      <input
        className="input-field max-w-sm"
        placeholder="Search controls…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {isLoading ? (
        <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : (
        <div className="card divide-y divide-base-800">
          {data?.items.map((c) => (
            <div key={c.id} className="p-4 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="text-ink-100 truncate">{c.title}</div>
                <div className="text-xs text-ink-500 font-mono mt-0.5 truncate">{c.rule_id} · {c.category}</div>
              </div>
              <SeverityBadge severity={c.severity} />
            </div>
          ))}
          {data?.items.length === 0 && (
            <div className="p-8 text-center text-ink-500">No controls discovered yet — run a scan first.</div>
          )}
        </div>
      )}
    </div>
  );
}
