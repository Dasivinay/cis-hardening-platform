import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listSchedules, createSchedule, toggleSchedule, deleteSchedule } from "../api/scheduling";
import { listContainers } from "../api/containers";
import { Skeleton } from "../components/Skeleton";
import { LuPlus, LuTrash2 } from "react-icons/lu";

const CRON_PRESETS = [
  { label: "Daily at 2am UTC", value: "0 2 * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Weekly (Sunday 3am UTC)", value: "0 3 * * 0" },
];

export function SchedulingPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [containerId, setContainerId] = useState("");
  const [cron, setCron] = useState(CRON_PRESETS[0].value);

  const { data: schedules, isLoading } = useQuery({ queryKey: ["schedules"], queryFn: listSchedules });
  const { data: containers } = useQuery({ queryKey: ["containers-for-schedule"], queryFn: () => listContainers() });

  const createMutation = useMutation({
    mutationFn: () =>
      createSchedule({
        container_id: containerId,
        engine: "openscap",
        benchmark_id: "xccdf_org.ssgproject.content_profile_cis_level1_server",
        cron_expression: cron,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      setShowForm(false);
      setContainerId("");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => toggleSchedule(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-100">Scheduled Scans</h1>
          <p className="text-ink-500 text-sm mt-1">Recurring benchmark runs, checked every minute by Celery Beat.</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="btn-primary flex items-center gap-2">
          <LuPlus size={16} /> New schedule
        </button>
      </div>

      {showForm && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-3">
            <select className="input-field" value={containerId} onChange={(e) => setContainerId(e.target.value)}>
              <option value="">Select target…</option>
              {containers?.items.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select className="input-field" value={cron} onChange={(e) => setCron(e.target.value)}>
              {CRON_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            <button
              className="btn-primary shrink-0"
              disabled={!containerId || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Saving…" : "Save"}
            </button>
          </div>
          {createMutation.isError && (
            <p className="text-status-fail text-sm">{(createMutation.error as any)?.response?.data?.message}</p>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : (
        <div className="card divide-y divide-base-800">
          {schedules?.items.map((s) => (
            <div key={s.id} className="p-4 flex items-center justify-between">
              <div>
                <div className="text-ink-100 font-mono text-sm">{s.cron_expression}</div>
                <div className="text-xs text-ink-500 mt-0.5">
                  {s.engine} · last run: {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "never"}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-ink-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={s.is_active}
                    onChange={(e) => toggleMutation.mutate({ id: s.id, is_active: e.target.checked })}
                  />
                  Active
                </label>
                <button onClick={() => deleteMutation.mutate(s.id)} className="p-2 rounded hover:bg-base-800 text-status-fail">
                  <LuTrash2 size={16} />
                </button>
              </div>
            </div>
          ))}
          {schedules?.items.length === 0 && (
            <div className="p-8 text-center text-ink-500">No recurring scans configured.</div>
          )}
        </div>
      )}
    </div>
  );
}
