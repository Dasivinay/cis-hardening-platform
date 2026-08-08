import { NavLink } from "react-router-dom";
import { LuLayoutDashboard, LuServer, LuScanLine, LuShieldCheck, LuFileClock, LuUsers, LuLogOut, LuCalendarClock } from "react-icons/lu";
import { useAuth } from "../context/AuthContext";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LuLayoutDashboard, roles: ["admin", "analyst", "viewer"] },
  { to: "/targets", label: "Targets", icon: LuServer, roles: ["admin", "analyst", "viewer"] },
  { to: "/scans", label: "Scans", icon: LuScanLine, roles: ["admin", "analyst", "viewer"] },
  { to: "/scheduling", label: "Scheduling", icon: LuCalendarClock, roles: ["admin", "analyst"] },
  { to: "/controls", label: "Controls", icon: LuShieldCheck, roles: ["admin", "analyst", "viewer"] },
  { to: "/audit", label: "Audit Log", icon: LuFileClock, roles: ["admin"] },
  { to: "/admin/users", label: "Users", icon: LuUsers, roles: ["admin"] },
];

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="w-60 shrink-0 bg-base-900 border-r border-base-700 flex flex-col h-screen sticky top-0">
      <div className="px-5 py-6">
        <span className="font-display font-semibold text-lg tracking-tight text-ink-100">SecHarden</span>
        <div className="text-xs text-ink-500 mt-0.5 font-mono">CIS Benchmarking Platform</div>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.filter((item) => !user || item.roles.includes(user.role)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-status-info/10 text-status-info border border-status-info/30"
                  : "text-ink-300 hover:bg-base-800 hover:text-ink-100 border border-transparent"
              )
            }
          >
            <item.icon size={16} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-base-700">
        <div className="px-3 pb-3">
          <div className="text-sm text-ink-100">{user?.full_name}</div>
          <div className="text-xs text-ink-500 font-mono uppercase">{user?.role}</div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-ink-300 hover:bg-base-800 hover:text-status-fail w-full transition-colors"
        >
          <LuLogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
