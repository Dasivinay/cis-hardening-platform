import clsx from "clsx";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-status-critical/15 text-status-critical border-status-critical/40",
  high: "bg-status-fail/15 text-status-fail border-status-fail/40",
  medium: "bg-status-warn/15 text-status-warn border-status-warn/40",
  low: "bg-status-info/15 text-status-info border-status-info/40",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={clsx(
        "text-xs font-mono uppercase tracking-wide px-2 py-0.5 rounded border",
        SEVERITY_STYLES[severity] || SEVERITY_STYLES.medium
      )}
    >
      {severity}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  pass: "bg-status-pass/15 text-status-pass border-status-pass/40",
  fail: "bg-status-fail/15 text-status-fail border-status-fail/40",
  error: "bg-status-critical/15 text-status-critical border-status-critical/40",
  notchecked: "bg-ink-500/15 text-ink-300 border-ink-500/40",
  notapplicable: "bg-ink-500/15 text-ink-500 border-ink-500/30",
  running: "bg-status-info/15 text-status-info border-status-info/40",
  completed: "bg-status-pass/15 text-status-pass border-status-pass/40",
  failed: "bg-status-fail/15 text-status-fail border-status-fail/40",
  queued: "bg-status-warn/15 text-status-warn border-status-warn/40",
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "text-xs font-mono uppercase tracking-wide px-2 py-0.5 rounded border",
        STATUS_STYLES[status] || STATUS_STYLES.notchecked
      )}
    >
      {status}
    </span>
  );
}
