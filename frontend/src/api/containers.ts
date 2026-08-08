import { apiClient } from "./client";

export interface TargetContainer {
  id: string;
  name: string;
  docker_container_id: string | null;
  image: string;
  status: string;
  ubuntu_version: string;
  created_by: string | null;
  created_at: string;
}

export async function listContainers(params: Record<string, string> = {}) {
  const { data } = await apiClient.get("/containers", { params });
  return data as { items: TargetContainer[]; total: number; page: number; pages: number };
}

export async function createContainer(name: string) {
  const { data } = await apiClient.post("/containers", { name });
  return data as TargetContainer;
}

export async function deleteContainer(id: string) {
  await apiClient.delete(`/containers/${id}`);
}

export async function startContainer(id: string) {
  const { data } = await apiClient.post(`/containers/${id}/start`);
  return data as TargetContainer;
}

export async function stopContainer(id: string) {
  const { data } = await apiClient.post(`/containers/${id}/stop`);
  return data as TargetContainer;
}

export async function restartContainer(id: string) {
  const { data } = await apiClient.post(`/containers/${id}/restart`);
  return data as TargetContainer;
}

export async function getContainerLogs(id: string) {
  const { data } = await apiClient.get(`/containers/${id}/logs`);
  return data.logs as string;
}
