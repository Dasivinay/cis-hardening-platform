import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { LuBell } from "react-icons/lu";
import clsx from "clsx";
import { listNotifications, markRead, markAllRead } from "../api/notifications";

const LEVEL_DOT: Record<string, string> = {
  info: "bg-status-info",
  success: "bg-status-pass",
  warning: "bg-status-warn",
  error: "bg-status-fail",
};

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => listNotifications(),
    refetchInterval: 20000,
  });

  const unreadCount = data?.items.filter((n) => !n.is_read).length ?? 0;

  const readMutation = useMutation({
    mutationFn: (id: string) => markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const readAllMutation = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-md hover:bg-base-800 text-ink-300"
        aria-label="Notifications"
      >
        <LuBell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-status-fail text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center font-mono">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-80 card shadow-xl z-50 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-base-700">
              <span className="text-sm text-ink-100 font-medium">Notifications</span>
              {unreadCount > 0 && (
                <button onClick={() => readAllMutation.mutate()} className="text-xs text-status-info hover:underline">
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto divide-y divide-base-800">
              {data?.items.length === 0 && <div className="p-6 text-center text-ink-500 text-sm">No notifications yet.</div>}
              {data?.items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => !n.is_read && readMutation.mutate(n.id)}
                  className={clsx("w-full text-left px-4 py-3 hover:bg-base-800 transition-colors", !n.is_read && "bg-base-800/40")}
                >
                  <div className="flex items-start gap-2">
                    <span className={clsx("w-1.5 h-1.5 rounded-full mt-1.5 shrink-0", LEVEL_DOT[n.level])} />
                    <div className="min-w-0">
                      <div className="text-sm text-ink-100">{n.title}</div>
                      {n.message && <div className="text-xs text-ink-500 mt-0.5 truncate">{n.message}</div>}
                      <div className="text-[10px] text-ink-500 font-mono mt-1">{new Date(n.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
