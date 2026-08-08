import { apiClient } from "./client";

export interface NotificationItem {
  id: string;
  title: string;
  message: string | null;
  level: "info" | "success" | "warning" | "error";
  is_read: boolean;
  created_at: string;
}

export async function listNotifications(unreadOnly = false) {
  const { data } = await apiClient.get("/notifications", { params: { unread_only: String(unreadOnly) } });
  return data as { items: NotificationItem[]; total: number };
}

export async function markRead(id: string) {
  const { data } = await apiClient.post(`/notifications/${id}/read`);
  return data as NotificationItem;
}

export async function markAllRead() {
  await apiClient.post("/notifications/read-all");
}
