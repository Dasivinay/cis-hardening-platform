import { apiClient } from "./client";

export interface ScheduledScan {
  id: string;
  container_id: string;
  engine: string;
  benchmark_id: string;
  cron_expression: string;
  is_active: boolean;
  last_run_at: string | null;
}

export async function listSchedules() {
  const { data } = await apiClient.get("/scheduled-scans");
  return data as { items: ScheduledScan[]; total: number };
}

export async function createSchedule(payload: { container_id: string; engine: string; benchmark_id: string; cron_expression: string }) {
  const { data } = await apiClient.post("/scheduled-scans", payload);
  return data as ScheduledScan;
}

export async function toggleSchedule(id: string, is_active: boolean) {
  const { data } = await apiClient.post(`/scheduled-scans/${id}/toggle`, { is_active });
  return data as ScheduledScan;
}

export async function deleteSchedule(id: string) {
  await apiClient.delete(`/scheduled-scans/${id}`);
}
