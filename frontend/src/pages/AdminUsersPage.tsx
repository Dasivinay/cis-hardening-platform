import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { Skeleton } from "../components/Skeleton";

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

async function listUsers() {
  const { data } = await apiClient.get("/users");
  return data as { items: AdminUser[] };
}

export function AdminUsersPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-users"], queryFn: listUsers });

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-100">Users</h1>
        <p className="text-ink-500 text-sm mt-1">Manage platform accounts and roles.</p>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-base-800/50">
              <tr className="text-left text-ink-500">
                <th className="px-4 py-3 font-normal">Name</th>
                <th className="px-4 py-3 font-normal">Email</th>
                <th className="px-4 py-3 font-normal">Role</th>
                <th className="px-4 py-3 font-normal">Status</th>
                <th className="px-4 py-3 font-normal">Last login</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((u) => (
                <tr key={u.id} className="border-t border-base-800">
                  <td className="px-4 py-3 text-ink-100">{u.full_name}</td>
                  <td className="px-4 py-3 text-ink-300 font-mono text-xs">{u.email}</td>
                  <td className="px-4 py-3 uppercase text-xs font-mono text-status-info">{u.role}</td>
                  <td className="px-4 py-3">
                    <span className={u.is_active ? "text-status-pass" : "text-status-fail"}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-500">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
