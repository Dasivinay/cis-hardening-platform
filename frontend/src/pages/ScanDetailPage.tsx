import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getScan, listScanControls } from "../api/scans";
import { apiClient } from "../api/client";
import { StatCard } from "../components/StatCard";
import { StatusBadge, SeverityBadge } from "../components/SeverityBadge";
import { Skeleton } from "../components/Skeleton";
import { LuDownload, LuFileText } from "react-icons/lu";

async function downloadReport(scanId: string, format: "pdf" | "html") {
  const response = await apiClient.get(`/reports/scan/${scanId}/${format}`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `scan-${scanId}.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data: scan, isLoading: scanLoading } = useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => getScan(scanId!),
    refetchInterval: (query) => (query.state.data?.status === "running" || query.state.data?.status === "queued" ? 3000 : false),
  });

  const { data: controls, isLoading: controlsLoading } = useQuery({
    queryKey: ["scan-controls", scanId, statusFilter, search],
    queryFn: () => listScanControls(scanId!, { ...(statusFilter ? { status: statusFilter } : {}), ...(search ? { search } : {}) }),
    enabled: !!scanId,
  });

  if (scanLoading || !scan) {
    return <div className="p-8"><Skeleton className="h-40" /></div>;
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-100">{scan.container_name}</h1>
          <p className="text-ink-500 text-sm mt-1 font-mono">{scan.benchmark_id}</p>
        </div>
        {scan.status === "completed" && (
          <div className="flex items-center gap-2">
            <button onClick={() => downloadReport(scan.id, "pdf")} className="btn-secondary flex items-center gap-2 text-sm">
              <LuDownload size={14} /> Export PDF
            </button>
            <button onClick={() => downloadReport(scan.id, "html")} className="btn-secondary flex items-center gap-2 text-sm">
              <LuFileText size={14} /> Export HTML
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Status" value={<StatusBadge status={scan.status} />} />
        <StatCard label="Score" value={scan.overall_score != null ? `${scan.overall_score}%` : "—"} accent="text-status-pass" />
        <StatCard label="Passed" value={scan.passed_controls} accent="text-status-pass" />
        <StatCard label="Failed" value={scan.failed_controls} accent="text-status-fail" />
      </div>

      {scan.status === "running" || scan.status === "queued" ? (
        <div className="card p-6 text-center text-ink-300">
          Scan in progress — this page refreshes automatically.
        </div>
      ) : scan.status === "failed" ? (
        <div className="space-y-4">
          <div className="card p-6 border-status-fail/40">
            <div className="text-status-fail font-medium mb-2">Scan failed</div>
            <p className="text-ink-100 text-sm whitespace-pre-wrap font-mono">
              {scan.error_message || "No error message was recorded."}
            </p>
          </div>
          {scan.oscap_stderr && (
            <div className="card p-6">
              <div className="text-status-fail text-sm mb-2">oscap stderr</div>
              <pre className="text-xs text-ink-500 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                {scan.oscap_stderr}
              </pre>
            </div>
          )}
          {scan.oscap_stdout && (
            <div className="card p-6">
              <div className="text-ink-300 text-sm mb-2">oscap stdout</div>
              <pre className="text-xs text-ink-500 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                {scan.oscap_stdout}
              </pre>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <input
              className="input-field max-w-xs"
              placeholder="Search controls…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {["", "pass", "fail", "error", "notchecked"].map((s) => (
              <button
                key={s || "all"}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-md text-sm border ${
                  statusFilter === s ? "bg-status-info/10 text-status-info border-status-info/30" : "border-base-700 text-ink-300 hover:bg-base-800"
                }`}
              >
                {s || "All"}
              </button>
            ))}
          </div>

          {controlsLoading ? (
            <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : (
            <div className="card divide-y divide-base-800">
              {controls?.items.map((r) => (
                <div key={r.id} className="p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-ink-100 truncate">{r.control.title}</div>
                      <div className="text-xs text-ink-500 font-mono mt-0.5 truncate">{r.control.rule_id}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <SeverityBadge severity={r.control.severity} />
                      <StatusBadge status={r.status} />
                    </div>
                  </div>
                </div>
              ))}
              {controls?.items.length === 0 && (
                <div className="p-8 text-center text-ink-500">No controls match this filter.</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
