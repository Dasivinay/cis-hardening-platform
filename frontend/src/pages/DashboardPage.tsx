import { useQuery } from "@tanstack/react-query";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { getDashboardSummary } from "../api/scans";
import { StatCard } from "../components/StatCard";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/SeverityBadge";
import { LuServer, LuScanLine, LuGauge, LuTriangleAlert } from "react-icons/lu";
import { Link } from "react-router-dom";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#FF3B6B",
  high: "#F1554C",
  medium: "#F5B942",
  low: "#4FA9E8",
};

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    refetchInterval: 15000,
  });

  const severityData = data
    ? Object.entries(data.failed_by_severity || {}).map(([severity, count]) => ({
        name: severity,
        value: count as number,
      }))
    : [];

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-100">Overview</h1>
        <p className="text-ink-500 text-sm mt-1">Fleet-wide benchmark posture, refreshed every 15s.</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Targets" value={data?.total_targets ?? 0} icon={<LuServer className="text-ink-500" size={18} />} />
            <StatCard label="Total Scans" value={data?.total_scans ?? 0} icon={<LuScanLine className="text-ink-500" size={18} />} />
            <StatCard
              label="Avg. Benchmark Score"
              value={data?.average_score != null ? `${data.average_score}%` : "N/A"}
              accent="text-status-pass"
              icon={<LuGauge className="text-ink-500" size={18} />}
            />
            <StatCard
              label="Failed Controls"
              value={data?.total_failed_controls ?? 0}
              accent="text-status-fail"
              icon={<LuTriangleAlert className="text-ink-500" size={18} />}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="card p-5 col-span-1">
              <h2 className="text-sm text-ink-300 mb-4">Failed Controls by Severity</h2>
              {severityData.length === 0 ? (
                <p className="text-ink-500 text-sm">No failures recorded yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={severityData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={3}>
                      {severityData.map((entry, i) => (
                        <Cell key={i} fill={SEVERITY_COLORS[entry.name] || "#6B7690"} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#161C2C", border: "1px solid #212A3E", borderRadius: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="card p-5 col-span-2">
              <h2 className="text-sm text-ink-300 mb-4">Score per Target (latest scan)</h2>
              {(data?.latest_scan_per_target?.length ?? 0) === 0 ? (
                <p className="text-ink-500 text-sm">No completed scans yet — run one from the Targets page.</p>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data.latest_scan_per_target}>
                    <CartesianGrid stroke="#212A3E" vertical={false} />
                    <XAxis dataKey="container_name" tick={{ fill: "#6B7690", fontSize: 12 }} />
                    <YAxis tick={{ fill: "#6B7690", fontSize: 12 }} domain={[0, 100]} />
                    <Tooltip contentStyle={{ background: "#161C2C", border: "1px solid #212A3E", borderRadius: 8 }} />
                    <Bar dataKey="overall_score" fill="#3DDC97" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="card p-5">
            <h2 className="text-sm text-ink-300 mb-4">Latest Scan per Target</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-base-700">
                  <th className="pb-2 font-normal">Target</th>
                  <th className="pb-2 font-normal">Status</th>
                  <th className="pb-2 font-normal">Score</th>
                  <th className="pb-2 font-normal">Passed / Failed</th>
                  <th className="pb-2 font-normal">Completed</th>
                </tr>
              </thead>
              <tbody>
                {data?.latest_scan_per_target?.map((s: any) => (
                  <tr key={s.id} className="border-b border-base-800 last:border-0">
                    <td className="py-2">
                      <Link to={`/scans/${s.id}`} className="text-status-info hover:underline">{s.container_name}</Link>
                    </td>
                    <td className="py-2"><StatusBadge status={s.status} /></td>
                    <td className="py-2 mono-stat">{s.overall_score != null ? `${s.overall_score}%` : "N/A"}</td>
                    <td className="py-2 mono-stat">
                      <span className="text-status-pass">{s.passed_controls}</span> / <span className="text-status-fail">{s.failed_controls}</span>
                    </td>
                    <td className="py-2 text-ink-500">{s.completed_at ? new Date(s.completed_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
