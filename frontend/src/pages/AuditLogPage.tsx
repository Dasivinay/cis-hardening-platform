import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { Skeleton } from "../components/Skeleton";

interface AuditEntry {
  id: string;
  user: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string;
}

async function listAudit() {
  const { data } = await apiClient.get("/audit");
  return data as { items: AuditEntry[] };
}

export function AuditLogPage() {
  const { data, isLoading } = useQuery({ queryKey: ["audit-log"], queryFn: listAudit });

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-100">Audit Log</h1>
        <p className="text-ink-500 text-sm mt-1">Every state-changing action taken on the platform.</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
      ) : (
        <div className="card divide-y divide-base-800 font-mono text-xs">
          {data?.items.map((entry) => (
            <div key={entry.id} className="px-4 py-3 flex items-center gap-4">
              <span className="text-ink-500 w-40 shrink-0">{new Date(entry.created_at).toLocaleString()}</span>
              <span className="text-status-info w-40 shrink-0 truncate">{entry.user}</span>
              <span className="text-ink-100 w-48 shrink-0">{entry.action}</span>
              <span className="text-ink-500 truncate">{entry.resource_type} {entry.resource_id}</span>
              <span className="text-ink-500 ml-auto shrink-0">{entry.ip_address}</span>
            </div>
          ))}
          {data?.items.length === 0 && <div className="p-8 text-center text-ink-500">No audit entries yet.</div>}
        </div>
      )}
    </div>
  );
}
