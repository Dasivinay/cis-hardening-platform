import { Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { TargetsPage } from "./pages/TargetsPage";
import { ScansPage } from "./pages/ScansPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ControlsPage } from "./pages/ControlsPage";
import { SchedulingPage } from "./pages/SchedulingPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AuditLogPage } from "./pages/AuditLogPage";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex">
      <Sidebar />
      <div className="flex-1 min-h-screen flex flex-col">
        <Topbar />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><Shell><DashboardPage /></Shell></ProtectedRoute>} />
      <Route path="/targets" element={<ProtectedRoute><Shell><TargetsPage /></Shell></ProtectedRoute>} />
      <Route path="/scans" element={<ProtectedRoute><Shell><ScansPage /></Shell></ProtectedRoute>} />
      <Route path="/scans/:scanId" element={<ProtectedRoute><Shell><ScanDetailPage /></Shell></ProtectedRoute>} />
      <Route path="/scheduling" element={<ProtectedRoute roles={["admin", "analyst"]}><Shell><SchedulingPage /></Shell></ProtectedRoute>} />
      <Route path="/controls" element={<ProtectedRoute><Shell><ControlsPage /></Shell></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute roles={["admin"]}><Shell><AuditLogPage /></Shell></ProtectedRoute>} />
      <Route path="/admin/users" element={<ProtectedRoute roles={["admin"]}><Shell><AdminUsersPage /></Shell></ProtectedRoute>} />
    </Routes>
  );
}
