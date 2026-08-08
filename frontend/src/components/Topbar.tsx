import { NotificationBell } from "./NotificationBell";

export function Topbar() {
  return (
    <header className="h-14 border-b border-base-700 flex items-center justify-end px-6 sticky top-0 bg-base-950/80 backdrop-blur z-40">
      <NotificationBell />
    </header>
  );
}
