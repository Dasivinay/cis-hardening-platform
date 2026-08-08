import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listContainers, createContainer, startContainer, stopContainer, restartContainer, deleteContainer } from "../api/containers";
import { triggerScan } from "../api/scans";
import { StatusBadge } from "../components/SeverityBadge";
import { Skeleton } from "../components/Skeleton";
import { LuPlus, LuPlay, LuSquare, LuRefreshCw, LuTrash2, LuScanLine } from "react-icons/lu";
import { useAuth } from "../context/AuthContext";

export function TargetsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "admin" || user?.role === "analyst";
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["containers"], queryFn: () => listContainers() });

  const createMutation = useMutation({
    mutationFn: (name: string) => createContainer(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      setNewName("");
      setShowCreate(false);
    },
  });

  const actionMutation = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "start" | "stop" | "restart" | "delete" }) => {
      if (action === "start") { await startContainer(id); return; }
      if (action === "stop") { await stopContainer(id); return; }
      if (action === "restart") { await restartContainer(id); return; }
      await deleteContainer(id);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["containers"] }),
  });

  const scanMutation = useMutation({
    mutationFn: (containerId: string) =>
      triggerScan(containerId, "openscap", "xccdf_org.ssgproject.content_profile_cis_level1_server"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scans"] }),
  });

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-100">Targets</h1>
          <p className="text-ink-500 text-sm mt-1">Docker-managed Ubuntu containers available for scanning.</p>
        </div>
        {canManage && (
          <button onClick={() => setShowCreate((v) => !v)} className="btn-primary flex items-center gap-2">
            <LuPlus size={16} /> New target
          </button>
        )}
      </div>

      {showCreate && (
        <div className="card p-4 flex items-center gap-3">
          <input
            className="input-field"
            placeholder="target name, e.g. web-prod-01"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button
            className="btn-primary shrink-0"
            disabled={!newName || createMutation.isPending}
            onClick={() => createMutation.mutate(newName)}
          >
            {createMutation.isPending ? "Creating…" : "Create"}
          </button>
        </div>
      )}
      {createMutation.isError && (
        <p className="text-status-fail text-sm">{(createMutation.error as any)?.response?.data?.message || "Failed to create target."}</p>
      )}

      {isLoading ? (
        <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : data && data.items.length > 0 ? (
        <div className="card divide-y divide-base-800">
          {data.items.map((c) => (
            <div key={c.id} className="p-4 flex items-center justify-between">
              <div>
                <div className="font-medium text-ink-100">{c.name}</div>
                <div className="text-xs text-ink-500 font-mono mt-0.5">{c.image} · Ubuntu {c.ubuntu_version}</div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={c.status} />
                {canManage && (
                  <div className="flex items-center gap-1">
                    <button title="Run scan" onClick={() => scanMutation.mutate(c.id)} className="p-2 rounded hover:bg-base-800 text-status-info">
                      <LuScanLine size={16} />
                    </button>
                    <button title="Start" onClick={() => actionMutation.mutate({ id: c.id, action: "start" })} className="p-2 rounded hover:bg-base-800 text-status-pass">
                      <LuPlay size={16} />
                    </button>
                    <button title="Stop" onClick={() => actionMutation.mutate({ id: c.id, action: "stop" })} className="p-2 rounded hover:bg-base-800 text-status-warn">
                      <LuSquare size={16} />
                    </button>
                    <button title="Restart" onClick={() => actionMutation.mutate({ id: c.id, action: "restart" })} className="p-2 rounded hover:bg-base-800 text-status-info">
                      <LuRefreshCw size={16} />
                    </button>
                    <button title="Delete" onClick={() => actionMutation.mutate({ id: c.id, action: "delete" })} className="p-2 rounded hover:bg-base-800 text-status-fail">
                      <LuTrash2 size={16} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-10 text-center text-ink-500">
          No targets yet. Create one to start scanning.
        </div>
      )}
    </div>
  );
}
