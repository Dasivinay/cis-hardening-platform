import { apiClient } from "./client";

export interface ScanSummary {
  id: string;
  container_id: string;
  container_name: string | null;
  engine: string;
  benchmark_id: string;
  status: string;
  overall_score: number | null;
  total_controls: number;
  passed_controls: number;
  failed_controls: number;
  error_controls: number;
  notchecked_controls: number;
  triggered_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  error_message: string | null;
  datastream_path: string | null;
  oscap_stdout: string | null;
  oscap_stderr: string | null;
}

export interface ScanResultControl {
  id: string;
  status: string;
  result_detail: string | null;
  control: {
    id: string;
    rule_id: string;
    title: string;
    description: string;
    severity: string;
    category: string;
  };
}

export async function listScans(params: Record<string, string> = {}) {
  const { data } = await apiClient.get("/scans", { params });
  return data as { items: ScanSummary[]; total: number; page: number; pages: number };
}

export async function getScan(id: string) {
  const { data } = await apiClient.get(`/scans/${id}`);
  return data as ScanSummary;
}

export async function listScanControls(scanId: string, params: Record<string, string> = {}) {
  const { data } = await apiClient.get(`/scans/${scanId}/controls`, { params });
  return data as { items: ScanResultControl[]; total: number; page: number; pages: number };
}

export async function triggerScan(container_id: string, engine: string, benchmark_id: string) {
  const { data } = await apiClient.post("/scans", { container_id, engine, benchmark_id });
  return data as ScanSummary;
}

export async function getDashboardSummary() {
  const { data } = await apiClient.get("/dashboard/summary");
  return data;
}

export async function getTrend(containerId: string) {
  const { data } = await apiClient.get(`/dashboard/trend/${containerId}`);
  return data as { container_id: string; trend: Array<{ scan_id: string; completed_at: string; score: number; passed: number; failed: number }> };
}
