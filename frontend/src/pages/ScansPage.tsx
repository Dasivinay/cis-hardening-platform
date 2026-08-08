import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listScans } from "../api/scans";
import { StatusBadge } from "../components/SeverityBadge";
import { Skeleton } from "../components/Skeleton";
import { LuSearch } from "react-icons/lu";

export function ScansPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["scans", status, page],
    queryFn: () => listScans({ ...(status ? { status } : {}), page: String(page) }),
  });

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-100">Scan History</h1>
        <p className="text-ink-500 text-sm mt-1">Every benchmark run across all targets.</p>
      </div>

      <div className="flex items-center gap-2">
        {["", "queued", "running", "completed", "failed"].map((s) => (
          <button
            key={s || "all"}
            onClick={() => { setStatus(s); setPage(1); }}
            className={`px-3 py-1.5 rounded-md text-sm border ${
              status === s ? "bg-status-info/10 text-status-info border-status-info/30" : "border-base-700 text-ink-300 hover:bg-base-800"
            }`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-base-800/50">
              <tr className="text-left text-ink-500">
                <th className="px-4 py-3 font-normal">Target</th>
                <th className="px-4 py-3 font-normal">Engine</th>
                <th className="px-4 py-3 font-normal">Status</th>
                <th className="px-4 py-3 font-normal">Score</th>
                <th className="px-4 py-3 font-normal">Triggered by</th>
                <th className="px-4 py-3 font-normal">Started</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((s) => (
                <tr key={s.id} className="border-t border-base-800 hover:bg-base-800/40">
                  <td className="px-4 py-3">
                    <Link to={`/scans/${s.id}`} className="text-status-info hover:underline">{s.container_name}</Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-300">{s.engine}</td>
                  <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                  <td className="px-4 py-3 mono-stat">{s.overall_score != null ? `${s.overall_score}%` : "—"}</td>
                  <td className="px-4 py-3 text-ink-500">{s.triggered_by}</td>
                  <td className="px-4 py-3 text-ink-500">{s.started_at ? new Date(s.started_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-500">No scans match this filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {data && data.pages > 1 && (
        <div className="flex items-center gap-2 justify-center">
          {[...Array(data.pages)].map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i + 1)}
              className={`w-8 h-8 rounded text-sm ${page === i + 1 ? "bg-status-info text-base-950" : "text-ink-300 hover:bg-base-800"}`}
            >
              {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
